// Host-confirmed sensitive control, not backend WritePolicy or memory storage.
async function memoryControl(client, name, args, commandId, showDialog) {
  const reject = code => ({ schemaVersion: 1, commandId: commandId || '', completed: false,
    error: { code, message: 'Memory action cancelled, unavailable or stale.', retryable: false } })
  const sessionId = client.view.sessionId, workspace = client.view.workspace, revision = client.view.stateRevision
  if (!sessionId || !client.view.status.ready) return reject('MEMORY_UNAVAILABLE')
  const frozen = JSON.parse(JSON.stringify(args))
  const validate = () => client.view.status.ready && client.view.sessionId === sessionId
    && client.view.workspace === workspace && client.view.stateRevision === revision
  if (frozen.consentSensitive === true || frozen.includeSensitive === true) {
    const answer = await showDialog({ name, workspace, write: frozen.consentSensitive === true, validate })
    if (answer.response !== 1) return { schemaVersion: 1, commandId: commandId || '', completed: false, canceled: true }
  }
  if (!validate()) {
    return reject('REVISION_CONFLICT')
  }
  return client.memory(name, frozen, commandId)
}
// A classification choice is confirmed before changing the checkbox. The opaque
// receipt is single-use and bound to the exact record revision and session.
function createMemoryEditControls(client, showDialog) {
  const crypto = require('node:crypto'), tokens = new Map()
  let busy = false
  const reject = (code, commandId='') => ({schemaVersion:1,commandId,completed:false,error:{code}})
  const canceled = commandId => ({schemaVersion:1,commandId:commandId||'',completed:false,canceled:true})
  const binding = () => ({sessionId:client.view.sessionId,workspace:client.view.workspace})
  const available = () => client.view.status.ready && !!client.view.sessionId
  const same = value => available() && value.sessionId===client.view.sessionId && value.workspace===client.view.workspace
  const validChoice = value => value && Object.keys(value).every(k=>['memoryId','revision','sensitive'].includes(k))
    && typeof value.memoryId==='string' && value.memoryId.length>0 && value.memoryId.length<=128
    && Number.isSafeInteger(value.revision) && value.revision>0 && typeof value.sensitive==='boolean'
  async function confirm(choice) {
    if(busy||!available()||!validChoice(choice))return reject('MEMORY_UNTRUSTED_INPUT')
    busy=true
    try {
      const scope=binding(),revision=client.view.stateRevision
      const validate=()=>same(scope)&&client.view.stateRevision===revision
      const answer=await showDialog({kind:choice.sensitive?'memory-classify-sensitive':'memory-classify-normal',workspace:scope.workspace,validate})
      if(!answer?.confirmed)return canceled()
      if(!validate())return reject('REVISION_CONFLICT')
      const now=Date.now()
      for(const [key,value] of tokens)if(value.expires<=now||!same(value)||value.memoryId===choice.memoryId)tokens.delete(key)
      if(tokens.size>=200)tokens.delete(tokens.keys().next().value)
      const token=crypto.randomBytes(32).toString('hex')
      tokens.set(token,{...scope,...choice,expires:now+10*60*1000})
      return {schemaVersion:1,commandId:'',completed:true,data:{token}}
    }finally{busy=false}
  }
  async function edit(args,commandId) {
    if(busy||!available()||!args||Object.keys(args).some(k=>k!=='records')||!Array.isArray(args.records)||!args.records.length||args.records.length>200)
      return reject('MEMORY_UNTRUSTED_INPUT',commandId)
    const rows=JSON.parse(JSON.stringify(args.records)),ids=new Set(),used=new Set()
    for(const row of rows){
      if(!row||Object.keys(row).some(k=>!['memoryId','revision','text','kind','scope','sensitive','consentToken'].includes(k))
        ||!validChoice({memoryId:row.memoryId,revision:row.revision,sensitive:row.sensitive})||ids.has(row.memoryId)
        ||typeof row.text!=='string'||typeof row.kind!=='string'||!['WORKSPACE','GLOBAL_PROFILE'].includes(row.scope))return reject('MEMORY_UNTRUSTED_INPUT',commandId)
      ids.add(row.memoryId)
      row.consentSensitive=false
      if(row.consentToken!==undefined){
        const receipt=tokens.get(row.consentToken)
        if(!receipt||receipt.expires<=Date.now()||!same(receipt)||receipt.memoryId!==row.memoryId||receipt.revision!==row.revision||receipt.sensitive!==row.sensitive||used.has(row.consentToken))return reject('MEMORY_SENSITIVE_DENIED',commandId)
        used.add(row.consentToken);row.consentSensitive=true
      }
      delete row.consentToken
    }
    busy=true
    try {
      const scope=binding(),revision=client.view.stateRevision
      const validate=()=>same(scope)&&client.view.stateRevision===revision
      if(rows.some(row=>row.sensitive&&!row.consentSensitive)){
        const answer=await showDialog({kind:'memory-write-sensitive',workspace:scope.workspace,validate})
        if(!answer?.confirmed)return canceled(commandId)
        for(const row of rows)if(row.sensitive)row.consentSensitive=true
      }
      if(!validate())return reject('REVISION_CONFLICT',commandId)
      for(const token of used)tokens.delete(token)
      return await client.memory('memory_edit',{records:rows},commandId)
    }finally{busy=false}
  }
  async function remove(args,commandId){
    if(busy||!available()||!args||Object.keys(args).some(key=>key!=='records')||!Array.isArray(args.records)||!args.records.length||args.records.length>200)return reject('MEMORY_UNTRUSTED_INPUT',commandId)
    const rows=JSON.parse(JSON.stringify(args.records)),ids=new Set()
    for(const row of rows){
      if(!row||Object.keys(row).some(key=>!['memoryId','revision'].includes(key))||!validChoice({...row,sensitive:false})||ids.has(row.memoryId))return reject('MEMORY_UNTRUSTED_INPUT',commandId)
      ids.add(row.memoryId)
    }
    busy=true
    try{
      const scope=binding(),revision=client.view.stateRevision
      const validate=()=>same(scope)&&client.view.stateRevision===revision
      const answer=await showDialog({kind:'memory-delete-records',fileCount:rows.length,workspace:scope.workspace,validate})
      if(!answer?.confirmed)return canceled(commandId)
      if(!validate())return reject('REVISION_CONFLICT',commandId)
      return await client.memory('memory_delete',{records:rows},commandId)
    }finally{busy=false}
  }
  return {confirm,edit,remove,isBusy:()=>busy}
}
module.exports = { memoryControl, createMemoryEditControls }
