require('./register_typescript.cjs')
const { test } = require('node:test')
const assert = require('node:assert/strict')
const { ModelOperations } = require('../src/model_operations.ts')

function fixture() {
  let id = 0, refreshes = 0, timerId = 0
  const sent = [], timers = new Map()
  const schedule = fn => { timers.set(++timerId, fn); return timerId }
  const cancel = id => timers.delete(id)
  const ops = new ModelOperations(frame => sent.push(frame), () => ++id, () => { refreshes++ }, schedule, cancel)
  return { ops, sent, timers, get refreshes() { return refreshes }, last() { return sent.at(-1) },
    expire() { const pending = [...timers.values()]; timers.clear(); for (const callback of pending) callback() } }
}
const catalog = { categories: ['General'], models: [{ name: 'owned:1b', display: 'Owned', category: 'General', params: '1B', size_gb: 1, description: 'Owned fixture', tags: [], installed: false }] }

test('Default timers preserve the browser global receiver instead of invoking native timers as controller methods', () => {
  const previousSchedule = globalThis.setTimeout, previousCancel = globalThis.clearTimeout
  let scheduled = 0, canceled = 0, id = 0
  globalThis.setTimeout = function (callback, delay) {
    assert.equal(this, globalThis, 'browser setTimeout requires the Window/global receiver')
    assert.equal(typeof callback, 'function'); assert.ok(delay > 0); scheduled++
    return 41
  }
  globalThis.clearTimeout = function () {
    assert.equal(this, globalThis, 'browser clearTimeout requires the Window/global receiver'); canceled++
  }
  try {
    const ops = new ModelOperations(() => {}, () => ++id)
    ops.refreshCatalog(); assert.equal(scheduled, 1)
    ops.receive({ type: 'catalog', id, data: catalog })
    assert.equal(ops.state.catalogLoading, false); assert.ok(canceled >= 2)
    ops.dispose()
  } finally {
    globalThis.setTimeout = previousSchedule; globalThis.clearTimeout = previousCancel
  }
})

test('Catalog uses matching request and a duplicate open does not dispatch twice', () => {
  const f = fixture(); f.ops.refreshCatalog(); f.ops.refreshCatalog()
  assert.equal(f.sent.length, 1); assert.equal(f.ops.state.catalogLoading, true)
  assert.equal(f.ops.receive({ type: 'catalog', id: 999, data: catalog }), false)
  assert.equal(f.ops.state.catalog, null)
  f.ops.receive({ type: 'catalog', id: f.last().id, data: catalog })
  assert.deepEqual(f.ops.state.catalog, catalog); assert.equal(f.ops.state.catalogLoading, false)
  assert.equal(f.timers.size, 0)
})

test('Hardware-fit progress is correlated, keeps loading active and preserves exact recommended variants',()=>{
  const f=fixture();f.ops.recommend();const request=f.last()
  const model={name:'public-owned:4b-q4_K_M',family:'public-owned',display:'public-owned',reason:'MEMORY_FIT',rank:1,installed:false,
    kind:'llm',tags:['tools'],description:'Public fixture',size_label:'2.5GB',size_gb:2.5,estimated_memory_gb:3.875,context_length:8192,gpu_fit:false}
  const recommendation={phase:'variants',scanned:1,total:5,unavailable:0,offline:false,stale:false,syncedAt:1000,budget_gb:7}
  assert.equal(f.ops.receive({id:request.id+99,type:'recommend_progress',models:[model],recommendation}),false)
  f.ops.receive({id:request.id,type:'recommend_progress',models:[model],recommendation})
  assert.equal(f.ops.state.recommending,true);assert.equal(f.ops.state.recommendations[0].name,model.name)
  assert.equal(f.ops.state.recommendationStatus.scanned,1)
  f.ops.receive({id:request.id,type:'recommend',models:[model],recommendation:{...recommendation,phase:'complete',scanned:5}})
  assert.equal(f.ops.state.recommending,false);assert.equal(f.ops.state.recommendationStatus.phase,'complete')
  assert.ok(f.sent.every(frame=>frame.type==='recommend'));f.ops.dispose()
})

test('Malformed fit metadata fails without accepting a fabricated fit or progress count',()=>{
  for(const recommendation of [{phase:'variants',scanned:5,total:1,unavailable:0,offline:false,stale:false,syncedAt:1000,budget_gb:7},{}]){
    const f=fixture();f.ops.recommend();f.ops.receive({id:f.last().id,type:'recommend_progress',models:[],recommendation})
    assert.equal(f.ops.state.recommending,false);assert.equal(f.ops.state.recommendError,'MODEL_RECOMMEND_FAILED');f.ops.dispose()
  }
})

test('A successful full synchronization refreshes recommendations after an older evaluation drains',()=>{
  const f=fixture();f.ops.recommend();const old=f.last();f.ops.sync();const sync=f.last()
  f.ops.receive({id:sync.id,type:'catalog_updated',data:{total:5}})
  assert.equal(f.sent.filter(frame=>frame.type==='recommend').length,1)
  f.ops.receive({id:old.id,type:'recommend',models:[],system:null})
  assert.equal(f.sent.filter(frame=>frame.type==='recommend').length,2)
  assert.equal(f.ops.state.recommending,true);assert.equal(f.ops.state.recommendations,null)
  f.ops.dispose()
})
test('Errors settle each corresponding spinner as localizable codes without raw server text', () => {
  const calls = [ ['refreshCatalog', [], 'catalogLoading', 'catalogError', 'MODEL_CATALOG_FAILED'],
    ['recommend', [], 'recommending', 'recommendError', 'MODEL_RECOMMEND_FAILED'],
    ['sync', [], 'updating', 'operationError', 'MODEL_SYNC_FAILED'],
    ['pull', ['owned:1b'], 'pulling', 'operationError', 'MODEL_DOWNLOAD_FAILED'],
    ['delete', ['owned:1b'], 'deleting', 'operationError', 'MODEL_DELETE_FAILED'] ]
  for (const [name, args, pending, error, code] of calls) {
    const f = fixture(); f.ops[name](...args)
    f.ops.receive({ type: 'error', id: f.last().id, message: 'sensitive-path-and-token' })
    assert.ok(!f.ops.state[pending]); assert.equal(f.ops.state[error], code)
    assert.ok(!JSON.stringify(f.ops.state).includes('sensitive'))
    assert.equal(f.timers.size, 0)
  }
})
test('Malformed catalog/recommend responses become clear errors instead of render exceptions', () => {
  const f = fixture(); f.ops.refreshCatalog()
  f.ops.receive({ type: 'catalog', id: f.last().id, data: { categories: [], models: [{}] } })
  assert.equal(f.ops.state.catalogError, 'MODEL_CATALOG_FAILED')
  f.ops.recommend(); f.ops.receive({ type: 'recommend', id: f.last().id, models: [{}] })
  assert.equal(f.ops.state.recommendError, 'MODEL_RECOMMEND_FAILED')
})
test('Optional catalog metadata must be render-safe; malformed strengths/date/context/rating are rejected', () => {
  const variants = [{ strengths: 'x' }, { strengths: [{}] }, { context_length: '32768' },
    { context_length: Infinity }, { context_length: -1 }, { release_date: {} },
    { ease_of_use: '5' }, { ease_of_use: 6 }, { ease_of_use: 2.5 }, { size_gb: -1 }]
  for (const optional of variants) {
    const f = fixture(); f.ops.refreshCatalog()
    f.ops.receive({ type: 'catalog', id: f.last().id, data: { ...catalog, models: [{ ...catalog.models[0], ...optional }] } })
    assert.equal(f.ops.state.catalog, null); assert.equal(f.ops.state.catalogLoading, false)
    assert.equal(f.ops.state.catalogError, 'MODEL_CATALOG_FAILED'); f.ops.dispose()
  }
  const f = fixture(); f.ops.refreshCatalog()
  const data = { ...catalog, models: [{ ...catalog.models[0], strengths: ['code'], context_length: 32768, release_date: '2026-10', ease_of_use: 5 }] }
  f.ops.receive({ type: 'catalog', id: f.last().id, data })
  assert.deepEqual(f.ops.state.catalog, data); assert.equal(f.ops.state.catalogError, null); f.ops.dispose()
})
test('Hardware JSX fields and recommendation numeric or boolean fields reject malformed payloads', () => {
  const model = { name: 'owned', display: 'Owned', reason: 'Owned', rank: 1, installed: false, size_gb: 1 }
  const system = { ram_gb: 32, chip: 'Owned', gpu: 'Owned', os: 'Windows', arch: 'x64' }
  for (const optional of [{ gpu: {} }, { chip: {} }, { os: [] }, { arch: 42 }, { ram_gb: NaN }, { ram_gb: Infinity }, { ram_gb: -1 }, { ram_gb: '32' }]) {
    const f = fixture(); f.ops.recommend()
    f.ops.receive({ type: 'recommend', id: f.last().id, models: [model], system: { ...system, ...optional } })
    assert.equal(f.ops.state.recommendations, null); assert.equal(f.ops.state.systemInfo, null)
    assert.equal(f.ops.state.recommendError, 'MODEL_RECOMMEND_FAILED'); assert.equal(f.ops.state.recommending, false); f.ops.dispose()
  }
  for (const optional of [{ size_gb: NaN }, { rank: {} }, { installed: 'true' }]) {
    const f = fixture(); f.ops.recommend()
    f.ops.receive({ type: 'recommend', id: f.last().id, models: [{ ...model, ...optional }], system })
    assert.equal(f.ops.state.recommendError, 'MODEL_RECOMMEND_FAILED'); f.ops.dispose()
  }
  const f = fixture(); f.ops.recommend()
  f.ops.receive({ type: 'recommend', id: f.last().id, models: [model], system: { ...system, ram_gb: null } })
  assert.equal(f.ops.state.recommendError, null); assert.equal(f.ops.state.systemInfo.ram_gb, null); f.ops.dispose()
})
test('Download remains one operation across modal detach/reopen; no select and no auto download', () => {
  const f = fixture(); const seen = []
  const detach = f.ops.subscribe(s => seen.push(s))
  assert.equal(f.sent.length, 0)
  assert.equal(f.ops.pull('owned:1b'), true); const request = f.last()
  assert.equal(f.ops.pull('owned:1b'), false); assert.equal(f.ops.delete('other:2b'), false)
  assert.equal(f.sent.length, 1); detach()
  f.ops.receive({ type: 'pull_progress', id: request.id, model: 'owned:1b', status: 'pulling', completed: 5, total: 10 })
  const reopened = []; const dispose = f.ops.subscribe(s => reopened.push(s))
  assert.equal(reopened[0].pulling, 'owned:1b'); assert.equal(reopened[0].pullProgress, 'pulling 50%')
  f.ops.receive({ type: 'pull_done', id: request.id, model: 'owned:1b' }); dispose()
  assert.equal(f.ops.state.pulling, null); assert.deepEqual(f.ops.state.operationNotice, { kind: 'downloaded', model: 'owned:1b' })
  assert.equal(f.refreshes, 1); assert.equal(f.last().type, 'catalog')
  assert.ok(!f.sent.some(x => ['switch_model', 'application_command'].includes(x.type)))
})
test('Wrong-model and unsolicited pull messages cannot complete a local download', () => {
  const f = fixture(); f.ops.receive({ type: 'pull_start', id: 123, model: 'external' })
  assert.equal(f.ops.state.pulling, null)
  f.ops.pull('owned:1b'); const request = f.last()
  assert.equal(f.ops.receive({ type: 'pull_done', id: request.id, model: 'other' }), false)
  assert.equal(f.ops.state.pulling, 'owned:1b'); assert.equal(f.ops.state.operationNotice, null)
  f.ops.dispose()
})
test('Delete is locked until exact completion, then inventory refreshes without changing active model', () => {
  const f = fixture(); f.ops.delete('owned:1b'); const request = f.last()
  assert.equal(f.ops.state.deleting, 'owned:1b'); assert.equal(f.ops.delete('other'), false)
  assert.equal(f.ops.pull('other'), false)
  f.ops.receive({ type: 'delete_done', id: request.id, model: 'owned:1b' })
  assert.equal(f.ops.state.deleting, null); assert.deepEqual(f.ops.state.operationNotice, { kind: 'deleted', model: 'owned:1b' })
  assert.equal(f.refreshes, 1); assert.ok(!f.sent.some(x => x.type === 'switch_model'))
  f.ops.dispose()
})
test('Sync and recommendations keep independent progress and only matching receipts acknowledge success', () => {
  const f = fixture(); f.ops.sync(); const sync = f.last(); f.ops.sync()
  assert.equal(f.sent.length, 1)
  f.ops.recommend(); const rec = f.last(); f.ops.recommend()
  assert.equal(f.sent.length, 2)
  f.ops.receive({ id: rec.id, type: 'recommend', models: [{ name: 'owned', display: 'Owned', reason: 'Owned', rank: 1, installed: false, size_gb: 1 }], system: { ram_gb: 32, chip: 'Owned', gpu: 'Owned', os: 'Windows', arch: 'x64' } })
  assert.equal(f.ops.state.recommending, false); assert.equal(f.ops.state.updating, true)
  f.ops.receive({ id: sync.id, type: 'catalog_updated', data: { added: 0, updated: 1, total: 1 } })
  assert.equal(f.ops.state.updating, false); assert.deepEqual(f.ops.state.operationNotice, { kind: 'synced' })
  assert.equal(f.last().type, 'catalog'); assert.equal(f.refreshes, 0)
  f.ops.dispose()
})
test('Timeout/disconnect never invent mutation success or silently permit a duplicate; late receipt may settle', () => {
  for (const end of ['expire', 'disconnect']) {
    const f = fixture(); f.ops.pull('owned'); const request = f.last()
    if (end === 'expire') f.expire(); else f.ops.disconnected()
    assert.equal(f.ops.state.pulling, null); assert.equal(f.ops.state.mutationUnconfirmed, true)
    assert.equal(f.ops.state.operationError, 'MODEL_OPERATION_UNCONFIRMED')
    assert.equal(f.ops.state.operationNotice, null); assert.equal(f.ops.pull('again'), false)
    f.ops.receive({ type: 'pull_done', id: request.id, model: 'owned' })
    assert.equal(f.ops.state.mutationUnconfirmed, false); assert.equal(f.ops.state.operationNotice.kind, 'downloaded')
    f.ops.dispose()
  }
})
test('Backend ready releases stale request bindings truthfully and refreshes inventory only', () => {
  const f = fixture(); f.ops.delete('owned'); const old = f.last()
  f.ops.disconnected(); f.ops.backendReady()
  assert.equal(f.ops.state.mutationUnconfirmed, false); assert.equal(f.ops.state.operationNotice, null)
  assert.equal(f.ops.state.operationError, 'MODEL_OPERATION_UNCONFIRMED'); assert.equal(f.last().type, 'catalog')
  assert.equal(f.ops.receive({ id: old.id, type: 'delete_done', model: 'owned' }), false)
  assert.equal(f.refreshes, 0); f.ops.dispose()
})
test('Fresh correlated progress may resume observation after timeout without claiming completion', () => {
  const f = fixture(); f.ops.pull('owned'); const request = f.last(); f.expire()
  f.ops.receive({ type: 'pull_progress', id: request.id, model: 'owned', status: 'pulling', completed: 3, total: 10 })
  assert.equal(f.ops.state.pulling, 'owned'); assert.equal(f.ops.state.pullProgress, 'pulling 30%')
  assert.equal(f.ops.state.operationError, null); assert.equal(f.ops.state.operationNotice, null)
  assert.equal(f.ops.pull('owned'), false); f.ops.dispose()
})
test('Read-only timeouts release spinners without a false empty-result success', () => {
  const f = fixture(); f.ops.refreshCatalog(); f.expire()
  assert.equal(f.ops.state.catalogLoading, false); assert.equal(f.ops.state.catalogError, 'MODEL_OPERATION_UNCONFIRMED')
  f.ops.recommend(); f.expire(); assert.equal(f.ops.state.recommending, false)
  assert.equal(f.ops.state.recommendations, null); f.ops.dispose()
})
test('A synchronous bridge failure is bounded and can be retried without exposing the exception', () => {
  let id = 0
  const ops = new ModelOperations(() => { throw new Error('private bridge internals') }, () => ++id)
  ops.pull('owned'); assert.equal(ops.state.pulling, null); assert.equal(ops.state.operationError, 'MODEL_DOWNLOAD_FAILED')
  assert.equal(ops.state.mutationUnconfirmed, false); assert.equal(ops.pull('again'), true)
  assert.ok(!JSON.stringify(ops.state).includes('private')); ops.dispose()
})
