// Explicit runner for real Application snapshots exported by the B6 harness.
// Discovery doubles in that corpus prove product contract parity, not native claims.
require('./register_typescript.cjs')
const assert=require('node:assert/strict')
const fs=require('node:fs')
const path=require('node:path')
const {DesktopApplicationClient}=require('../electron/application_client.ts')

const input=process.env.NOVA_B6_DESKTOP_SNAPSHOT_PATH
assert(input && path.isAbsolute(input),'Owned temp Application snapshot path is required; this runner does not skip.')
const resolved=fs.realpathSync(input),repo=path.resolve(__dirname,'..','..')
assert(path.relative(repo,resolved).startsWith('..'),'Runtime snapshots must be outside the repository.')
const corpus=JSON.parse(fs.readFileSync(resolved,'utf8'))
assert.equal(corpus.schemaVersion,1)
assert.equal(corpus.source,'AgentSessionCoordinator.get_snapshot')
assert.equal(corpus.nativeCertification,false)
assert.deepEqual(corpus.cases.map(c=>c.name).sort(),['both_available','both_unavailable','browser_only','fetch_only'])
const results=[]
for (const entry of corpus.cases) {
  const snapshot=entry.snapshot, sent=[]
  assert.equal(snapshot.services.webCapabilitiesV12.schema,'WEB_CAPABILITIES_V12_1')
  const client=new DesktopApplicationClient(frame=>sent.push(frame),()=>{})
  client.receive({type:'ready',sessionId:snapshot.sessionId,tools:[]})
  client.receive({type:'snapshot',id:sent.at(-1).id,data:snapshot})
  assert.deepEqual(client.view.webCapabilitiesV12,snapshot.services.webCapabilitiesV12)
  assert.deepEqual(client.view.webV12,snapshot.services.webV12)
  const cf=client.view.webCapabilitiesV12.controlledFetch,ib=client.view.webCapabilitiesV12.interactiveBrowser
  assert.equal(cf.available.status,'KNOWN');assert.equal(ib.available.status,'KNOWN')
  assert.equal(cf.available.value,entry.expectedControlledFetchAvailable)
  assert.equal(ib.available.value,entry.expectedInteractiveBrowserAvailable)
  assert.equal(ib.networkIsolation.value,'NOT_PROVIDED')
  assert.equal(ib.controlClass.value,'HOST_UNISOLATED')
  assert.equal(snapshot.services.activeWeb.capabilities.available.value===true,false)
  const authorityFields=new Set(['grant','approval','networkProofRef','elementRef','browserSession',
    'cookie','credential','fileSelectionRef','stagingRef','takeoverRef','operationTicket'])
  function closedMetadata(value) {
    if (!value || typeof value!=='object') return
    for (const [key,child] of Object.entries(value)) {
      assert(!authorityFields.has(key),'Authority cannot appear in V12 capability metadata')
      closedMetadata(child)
    }
  }
  closedMetadata(client.view.webCapabilitiesV12)
  assert.equal(sent.filter(frame=>frame.type==='application_command'||frame.type==='browser_control').length,0)
  results.push({name:entry.name,projection:'PASS',authorityMetadataAbsent:true,automaticEffects:0})
}
process.stdout.write(JSON.stringify({schemaVersion:1,scope:'APPLICATION_CONTRACT_PARITY',
  nativeCertification:false,desktopClient:'DesktopApplicationClient',cases:results},null,2)+'\n')
