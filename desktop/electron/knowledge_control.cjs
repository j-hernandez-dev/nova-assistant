// Main-owned picker result is the only file-path authority for ingestion.
// Renderer controls accept IDs only; previews/read-file are not ingestion.
const ID_ACTIONS = new Set(['source_list','source_status','source_promote','source_delete','source_cancel','source_detail'])
const reject = code => ({schemaVersion:1,commandId:'',accepted:false,createdIds:{},
  error:{code,message:'Source selection unavailable, cancelled or stale.',retryable:false}})
async function pickKnowledge(client, showPicker) {
  const {sessionId,workspace,stateRevision} = client.view
  if (!sessionId || !client.view.status.ready) return reject('KNOWLEDGE_UNAVAILABLE')
  const picked = await showPicker()
  if (picked.canceled || !Array.isArray(picked.filePaths) || picked.filePaths.length !== 1 ||
      typeof picked.filePaths[0] !== 'string') return reject('IMPORT_CANCELLED')
  if (client.view.sessionId !== sessionId || client.view.workspace !== workspace ||
      client.view.stateRevision !== stateRevision) return reject('REVISION_CONFLICT')
  return client.knowledge('source_import', {path:picked.filePaths[0],scope:'SESSION'})
}
function knowledgeControl(client,name,args,commandId) {
  const keys = {source_import_url:['url','scope'],source_refresh_url:['sourceId','url'],source_detail:['sourceId','revisionId']}
  const allowed=(Object.hasOwn(keys,name)?keys[name]:null) || (ID_ACTIONS.has(name) ? [name==='source_cancel'?'operationId':'sourceId'] : null)
  if (!allowed || !args || Array.isArray(args) || typeof args !== 'object' ||
      Object.keys(args).some(k => !allowed.includes(k))) {
    return Promise.resolve(reject('SOURCE_NOT_AUTHORIZED'))
  }
  return client.knowledge(name,args,commandId)
}
async function hostSelection(client,name,sourceId,select) {
  const {sessionId,workspace,stateRevision}=client.view
  if (!sessionId || !client.view.status.ready) return reject('KNOWLEDGE_UNAVAILABLE')
  const picked=await select()
  const path=name==='source_export'?picked.filePath:picked.filePaths?.length===1?picked.filePaths[0]:null
  if(picked.canceled || typeof path!=='string')return reject('IMPORT_CANCELLED')
  if(client.view.sessionId!==sessionId || client.view.workspace!==workspace || client.view.stateRevision!==stateRevision)return reject('REVISION_CONFLICT')
  return client.knowledge(name,{sourceId,path})
}
async function remoteKnowledge(client,args,showConfirm,commandId) {
  if(!client.view.sessionId || !client.view.status.ready)return reject('KNOWLEDGE_UNAVAILABLE')
  if(!args || !Object.hasOwn(args,'sourceId') || !Object.hasOwn(args,'allowed') || Object.keys(args).some(k=>!['sourceId','allowed'].includes(k)) || typeof args.sourceId!=='string' || typeof args.allowed!=='boolean')return reject('SOURCE_NOT_AUTHORIZED')
  const frozen=JSON.parse(JSON.stringify(args));const {sessionId,workspace,stateRevision}=client.view
  if(frozen.allowed) {
    const answer=await showConfirm()
    if(answer.response!==1)return reject('REMOTE_FORWARDING_DENIED')
    if(client.view.sessionId!==sessionId || client.view.workspace!==workspace || client.view.stateRevision!==stateRevision)return reject('REVISION_CONFLICT')
  }
  return client.knowledge('source_remote',frozen,commandId)
}
module.exports = {pickKnowledge,knowledgeControl,hostSelection,remoteKnowledge}
