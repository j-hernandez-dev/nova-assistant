// Main-owned risk acknowledgement. Renderer input requests configuration only.
const path=require('node:path')
const RISK_ACKNOWLEDGEMENT_VERSION = 'IB_V12_RISK_1'
const RISK_MESSAGE = 'Interactive Browser uses a real browser engine.'
const RISK_DETAIL = 'Nova does not provide exhaustive network isolation for this capability. '
  + 'It is not a hostile-site network sandbox.\n\n'
  + 'Enabling this feature does not approve remote mutations, uploads, downloads or login side effects. '
  + 'Each action still follows Policy and any required Approval/Grant.'
const reject = code => ({schemaVersion:1,error:{code,
  message:'Web host control was not completed.',retryable:false}})

async function configureWebV12(client, request, showRiskDialog, commandId) {
  if (!request || typeof request !== 'object' || Array.isArray(request) ||
      Object.keys(request).length !== 2 ||
      !Object.hasOwn(request,'controlledFetchEnabled') || !Object.hasOwn(request,'interactiveBrowserEnabled') ||
      typeof request.controlledFetchEnabled !== 'boolean' || typeof request.interactiveBrowserEnabled !== 'boolean') {
    return reject('WEB_V12_CONFIGURATION_INVALID')
  }
  const {sessionId,workspace,stateRevision}=client.view
  if (!sessionId || !client.view.status.ready) return reject('WEB_V12_APPLICATION_UNAVAILABLE')
  const frozen={controlledFetchEnabled:request.controlledFetchEnabled,
    interactiveBrowserEnabled:request.interactiveBrowserEnabled}
  if (frozen.interactiveBrowserEnabled) {
    const answer=await showRiskDialog({message:RISK_MESSAGE,detail:RISK_DETAIL})
    if (answer?.response!==1) return reject('WEB_V12_RISK_ACKNOWLEDGEMENT_DENIED')
  }
  if (!client.view.status.ready || client.view.sessionId!==sessionId || client.view.workspace!==workspace ||
      client.view.stateRevision!==stateRevision) return reject('REVISION_CONFLICT')
  return client.browser('configure_web_v12',{...frozen,acknowledgementVersion:RISK_ACKNOWLEDGEMENT_VERSION},commandId)
}
async function selectWebV12Upload(client, operationId, showPicker, commandId) {
  if (typeof operationId!=='string' || !operationId || operationId.length>128) return reject('BROWSER_UPLOAD_SELECTION_INVALID')
  const {sessionId,workspace,stateRevision}=client.view
  const pending=client.view.webV12?.uploadRequests?.find(item=>item.operationId===operationId)
  if (!sessionId || !client.view.status.ready || !pending) return reject('BROWSER_UPLOAD_SELECTION_UNAVAILABLE')
  const fingerprint=JSON.stringify(pending)
  const selected=await showPicker({origin:pending.origin,label:pending.label})
  if (selected?.canceled || !Array.isArray(selected?.filePaths) || selected.filePaths.length!==1 ||
      typeof selected.filePaths[0]!=='string' || !path.isAbsolute(selected.filePaths[0])) {
    return reject('BROWSER_UPLOAD_SELECTION_CANCELLED')
  }
  const current=client.view.webV12?.uploadRequests?.find(item=>item.operationId===operationId)
  if (!client.view.status.ready || client.view.sessionId!==sessionId || client.view.workspace!==workspace ||
      client.view.stateRevision!==stateRevision || !current || JSON.stringify(current)!==fingerprint) return reject('REVISION_CONFLICT')
  // Private host path is never returned to renderer or stored in its projection.
  return client.browser('select_upload',{operationId,path:selected.filePaths[0]},commandId)
}
async function finishWebV12Takeover(client, takeoverRef, showConfirm, commandId) {
  if (typeof takeoverRef!=='string' || !takeoverRef || takeoverRef.length>128) return reject('BROWSER_TAKEOVER_REQUEST_INVALID')
  const {sessionId,workspace,stateRevision}=client.view
  const pending=client.view.webV12?.takeoverRequests?.find(item=>item.takeoverRef===takeoverRef)
  if (!sessionId || !client.view.status.ready || !pending || client.view.webV12?.browserState==='blocked') {
    return reject('BROWSER_TAKEOVER_REQUEST_UNAVAILABLE')
  }
  const fingerprint=JSON.stringify(pending),deadline=Date.parse(pending.deadline)
  if (!Number.isFinite(deadline) || Date.now()>=deadline) return reject('BROWSER_TAKEOVER_EXPIRED')
  const answer=await showConfirm({reason:pending.reason})
  if (answer?.response!==1) return reject('BROWSER_TAKEOVER_FINISH_CANCELLED')
  const current=client.view.webV12?.takeoverRequests?.find(item=>item.takeoverRef===takeoverRef)
  if (!client.view.status.ready || client.view.sessionId!==sessionId || client.view.workspace!==workspace ||
      client.view.stateRevision!==stateRevision || client.view.webV12?.browserState==='blocked' ||
      !current || JSON.stringify(current)!==fingerprint || Date.now()>=deadline) return reject('REVISION_CONFLICT')
  // This authenticates the human control path, never a login or remote Approval.
  // Application must verify terminal continuity, change epoch and observe afresh.
  return client.browser('finish_takeover',{takeoverRef,authenticated:false},commandId)
}
module.exports={configureWebV12,selectWebV12Upload,finishWebV12Takeover,RISK_ACKNOWLEDGEMENT_VERSION,RISK_MESSAGE,RISK_DETAIL}
