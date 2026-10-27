require('./register_typescript.cjs')
const {test}=require('node:test'),assert=require('node:assert/strict')
const {MemoryProposalNotifications,proposalNotificationIds}=require('../src/memory_proposal_notifications.ts')
const row=(id,job='job')=>({jobId:job,revision:1,proposal:{proposalId:id,text:'Private proposed text'}})
test('Window and tab acknowledge independently, without resolving pending proposals',()=>{
 const notifications=new MemoryProposalNotifications(),rows=[row('a'),row('b')]
 notifications.observe(rows);assert.deepEqual(notifications.counts,{window:2,tab:2})
 notifications.setWindowVisible(true);assert.deepEqual(notifications.counts,{window:0,tab:2})
 notifications.setWindowVisible(false);notifications.observe(rows);assert.deepEqual(notifications.counts,{window:0,tab:2})
 notifications.setTabVisible(true);assert.deepEqual(notifications.counts,{window:0,tab:0})
 notifications.setTabVisible(false);notifications.observe(rows);assert.deepEqual(notifications.counts,{window:0,tab:0})
 assert.equal(rows.length,2)
})
test('New identities notify even when the number of pending proposals stays the same',()=>{
 const notifications=new MemoryProposalNotifications()
 notifications.observe([row('a')]);notifications.setWindowVisible(true);notifications.setTabVisible(true)
 notifications.setWindowVisible(false);notifications.setTabVisible(false)
 notifications.observe([row('b')]);assert.deepEqual(notifications.counts,{window:1,tab:1})
 notifications.observe([]);assert.deepEqual(notifications.counts,{window:0,tab:0})
})
test('While visible, each surface acknowledges arrivals only for its own counter',()=>{
 const notifications=new MemoryProposalNotifications()
 notifications.setWindowVisible(true);notifications.observe([row('a')]);assert.deepEqual(notifications.counts,{window:0,tab:1})
 notifications.setTabVisible(true);notifications.observe([row('a'),row('b')]);assert.deepEqual(notifications.counts,{window:0,tab:0})
 notifications.setTabVisible(false);notifications.observe([row('a'),row('b'),row('c')]);assert.deepEqual(notifications.counts,{window:0,tab:1})
})
test('Only identity acknowledgements persist; restoring a profile does not renotify old proposals',()=>{
 let saved=null;const storage={load:()=>saved,save:value=>saved=structuredClone(value)}
 const notifications=new MemoryProposalNotifications(storage)
 notifications.observe([row('a')]);notifications.setWindowVisible(true)
 assert.doesNotMatch(JSON.stringify(saved),/Private|text|revision/)
 const restored=new MemoryProposalNotifications(storage);restored.observe([row('a')])
 assert.deepEqual(restored.counts,{window:0,tab:1})
 restored.setTabVisible(true)
 const restarted=new MemoryProposalNotifications(storage);restarted.observe([row('a'),row('b')])
 assert.deepEqual(restarted.counts,{window:1,tab:1})
})
test('Unread state is isolated between storage scopes and survives inaccessible presentation storage',()=>{
 const A=new MemoryProposalNotifications(),B=new MemoryProposalNotifications()
 A.observe([row('a')]);B.observe([row('a')]);A.setWindowVisible(true)
 assert.deepEqual(B.counts,{window:1,tab:1})
 const broken=new MemoryProposalNotifications({load(){throw Error('blocked')},save(){throw Error('full')}})
 broken.observe([row('a')]);broken.setWindowVisible(true);assert.deepEqual(broken.counts,{window:0,tab:1})
})
test('Malformed or incomplete inspection cannot clear unread state; repeated rows are deduplicated',()=>{
 const notifications=new MemoryProposalNotifications()
 notifications.observe([row('a'),row('a'),row('a','other-job')]);assert.deepEqual(notifications.counts,{window:2,tab:2})
 for(const value of [null,{},[{}],Array.from({length:513},()=>row('x'))]){
  assert.equal(notifications.observe(value),false);assert.deepEqual(notifications.counts,{window:2,tab:2})
 }
 assert.deepEqual(proposalNotificationIds([row('a')]),['["job","a"]'])
})
