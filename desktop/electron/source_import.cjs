const fs=require('node:fs')
const path=require('node:path')
const failure=(code,imported=0)=>({completed:false,imported,error:{code}})

/** Paths come from the native picker or webUtils in the isolated preload.
 * Each accepted import is observed to completion before submitting the next.
 * The lease keeps project switches and other storage mutations out of a batch.
 */
function createSourceImporter(client,options){
  let busy=false
  async function run(select){
    if(busy||options.isBlocked?.()||!client.view?.status?.ready||!client.view.sessionId)return failure('PROJECT_BUSY')
    const sessionId=client.view.sessionId,workspace=client.view.workspace,revision=client.view.stateRevision
    const valid=()=>client.view.sessionId===sessionId&&client.view.workspace===workspace&&client.view.status.ready&&!client.view.recovering&&!client.view.gap&&!client.view.activeTurnId&&!client.view.activeGenerationId&&!client.modelDownloadBusy?.()
    busy=true;options.onBusy?.(true)
    let imported=0
    const sourceIds=[]
    const failed=code=>({...failure(code,imported),sourceIds:[...sourceIds]})
    try{
      const picked=await select()
      if(picked.canceled)return {completed:false,canceled:true,imported:0}
      if(!valid()||client.view.stateRevision!==revision)return failure('REVISION_CONFLICT')
      const paths=picked.filePaths
      if(!Array.isArray(paths)||!paths.length||paths.length>100||new Set(paths).size!==paths.length||paths.some(value=>typeof value!=='string'||!path.isAbsolute(value)||value.length>32768||value.includes('\0')))return failure('SOURCE_NOT_AUTHORIZED')
      // Validate the whole batch before acquiring any content.
      try{if(paths.some(value=>!fs.statSync(value).isFile()))return failure('SOURCE_NOT_AUTHORIZED')}
      catch{return failure('SOURCE_NOT_AUTHORIZED')}
      for(const selectedPath of paths){
        if(!valid())return failed('REVISION_CONFLICT')
        const receipt=await client.knowledge('source_import',{path:selectedPath,scope:'WORKSPACE'})
        if(!receipt.accepted)return failed(receipt.error?.code||'SOURCE_IMPORT_UNKNOWN')
        const operationId=receipt.createdIds?.operationId
        if(!operationId)return failed('SOURCE_IMPORT_UNKNOWN')
        const deadline=Date.now()+180000
        let finished=false
        while(Date.now()<deadline){
          if(!valid())return failed('SOURCE_IMPORT_UNKNOWN')
          const operation=client.view.knowledgeOperations?.find(item=>item.operationId===operationId)
          const status=operation?.status?.toLowerCase()
          if(status&&status!=='running'&&status!=='pending'){
            if(status!=='completed'||operation.result?.error)return failed(operation.result?.error?.code||'SOURCE_IMPORT_FAILED')
            if(typeof operation.result?.sourceId==='string'&&!sourceIds.includes(operation.result.sourceId))sourceIds.push(operation.result.sourceId)
            finished=true;imported++;break
          }
          await new Promise(resolve=>setTimeout(resolve,40))
        }
        if(!finished)return failed('SOURCE_IMPORT_UNKNOWN')
      }
      return {completed:true,imported,sourceIds}
    }catch{return failed('SOURCE_IMPORT_UNKNOWN')}
    finally{busy=false;options.onBusy?.(false)}
  }
  return {pick:()=>run(options.pick),drop:paths=>run(async()=>({canceled:false,filePaths:paths})),isBusy:()=>busy}
}
module.exports={createSourceImporter}
