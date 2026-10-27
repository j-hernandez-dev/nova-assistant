const fs = require('node:fs')
const path = require('node:path')
const crypto = require('node:crypto')
const MAX_BYTES = 16 * 1024 * 1024
const copy = {
  es:{open:'Importar recuerdos',save:'Exportar recuerdos',select:'Importar',export:'Exportar',filter:'Recuerdos de Nova'},
  en:{open:'Import memories',save:'Export memories',select:'Import',export:'Export',filter:'Nova memories'},
}
const failure = (code,unknown=false) => ({schemaVersion:1,commandId:'',completed:false,error:{code,outcomeUnknown:unknown,retryable:false,message:'Memory action could not complete.'}})
const canceled = () => ({schemaVersion:1,commandId:'',completed:false,canceled:true})

function readBackup(filename) {
  if(fs.lstatSync(filename).isSymbolicLink())throw Error('MEMORY_IMPORT_INVALID')
  const fd=fs.openSync(filename,fs.constants.O_RDONLY|(fs.constants.O_NOFOLLOW||0))
  try{
    const before=fs.fstatSync(fd)
    if(!before.isFile())throw Error('MEMORY_IMPORT_INVALID')
    if(before.size>MAX_BYTES)throw Error('MEMORY_TRANSFER_TOO_LARGE')
    const buffer=Buffer.alloc(MAX_BYTES+1);let size=0,n
    while(size<buffer.length&&(n=fs.readSync(fd,buffer,size,buffer.length-size,null)))size+=n
    if(size>MAX_BYTES)throw Error('MEMORY_TRANSFER_TOO_LARGE')
    const after=fs.fstatSync(fd)
    if(before.size!==after.size||before.mtimeMs!==after.mtimeMs)throw Error('MEMORY_IMPORT_INVALID')
    try{return JSON.parse(buffer.subarray(0,size).toString('utf8').replace(/^\uFEFF/,''))}catch{throw Error('MEMORY_IMPORT_INVALID')}
  }finally{fs.closeSync(fd)}
}
function writeBackup(filename,value) {
  const data=Buffer.from(JSON.stringify(value,null,2)+'\n','utf8')
  if(data.length>MAX_BYTES)throw Error('MEMORY_TRANSFER_TOO_LARGE')
  if(fs.existsSync(filename)&&fs.lstatSync(filename).isSymbolicLink())throw Error('MEMORY_EXPORT_FAILED')
  const temporary=path.join(path.dirname(filename),'.nova-memory-'+crypto.randomBytes(16).toString('hex')+'.tmp')
  let fd
  try{
    fd=fs.openSync(temporary,'wx',0o600);fs.writeFileSync(fd,data);fs.fsyncSync(fd);fs.closeSync(fd);fd=undefined
    fs.renameSync(temporary,filename)
  }finally{if(fd!==undefined)fs.closeSync(fd);if(fs.existsSync(temporary))fs.unlinkSync(temporary)}
}

function createMemoryFileControls({client,projects,confirm,pickOpen,pickSave,getLocale,isBlocked=()=>false,isProtected=()=>false}) {
  let busy=false
  function ready(){const v=client.view;return v.status.ready&&v.status.connected!==false&&!!v.sessionId&&!v.recovering&&!v.activeTurnId&&!v.activeGenerationId
    &&!v.approvals?.length&&!v.inputs?.length&&!v.memory?.maintenanceBusy&&!client.workspaceBusy()&&!isBlocked()}
  async function run(action){
    if(busy||!ready())return failure('PROJECT_BUSY')
    busy=true
    const start=client.view,identity={sessionId:start.sessionId,workspace:start.workspace,revision:start.stateRevision}
    const valid=()=>ready()&&client.view.sessionId===identity.sessionId&&client.view.workspace===identity.workspace&&client.view.stateRevision===identity.revision
    try{return await action(valid,identity)}
    catch(error){return failure(['MEMORY_IMPORT_INVALID','MEMORY_TRANSFER_TOO_LARGE'].includes(error?.message)?error.message:'MEMORY_FILE_OPERATION_FAILED')}
    finally{busy=false}
  }
  async function transfer(kind,includeSensitive=false){
    if(!['import','export'].includes(kind)||typeof includeSensitive!=='boolean')return failure('MEMORY_UNTRUSTED_INPUT')
    return run(async(valid,identity)=>{
      if(kind==='import'||includeSensitive){
        const decision=await confirm({kind:kind==='import'?'memory-import':'memory-export-sensitive',validate:valid})
        if(!decision.confirmed)return canceled()
      }
      if(!valid())return failure('REVISION_CONFLICT')
      const t=copy[getLocale()==='en'?'en':'es']
      const picked=kind==='import'?await pickOpen({title:t.open,buttonLabel:t.select,properties:['openFile'],filters:[{name:t.filter,extensions:['json']}]}):
        await pickSave({title:t.save,buttonLabel:t.export,defaultPath:'nova-memories.json',filters:[{name:t.filter,extensions:['json']}]})
      if(picked.canceled)return canceled()
      if(!valid())return failure('REVISION_CONFLICT')
      if(kind==='import'){
        const filename=picked.filePaths?.[0]
        if(typeof filename!=='string'||!filename)return canceled()
        const backup=readBackup(filename)
        if(!valid())return failure('REVISION_CONFLICT')
        return client.memory('memory_import',{backup})
      }
      if(typeof picked.filePath!=='string'||!picked.filePath)return canceled()
      const filename=/\.json$/i.test(picked.filePath)?picked.filePath:picked.filePath+'.json'
      if(isProtected(filename))return failure('MEMORY_EXPORT_FAILED')
      const result=await client.memory('memory_export_all',{includeSensitive})
      if(!result.completed)return result
      if(client.view.sessionId!==identity.sessionId||client.view.workspace!==identity.workspace)return failure('REVISION_CONFLICT')
      writeBackup(filename,result.data)
      return {...result,data:{exported:result.data?.records?.length||0}}
    })
  }
  async function projectAccess(projectPath,enabled){
    if(typeof projectPath!=='string'||typeof enabled!=='boolean')return failure('MEMORY_UNTRUSTED_INPUT')
    return run(async(valid)=>{
      const folder=projects()?.folders.find(p=>p.path===projectPath)
      const current=()=>{try{return valid()&&projects()?.folders.some(p=>p.path===projectPath)&&fs.realpathSync(projectPath)===projectPath}catch{return false}}
      if(!folder||!current())return failure('PROJECT_NOT_REGISTERED')
      if(enabled){const decision=await confirm({kind:'memory-sensitive-access',projectName:folder.name,path:folder.path,validate:current});if(!decision.confirmed)return canceled()}
      if(!current())return failure('REVISION_CONFLICT')
      return client.memory('memory_project_access',{projectPath,enabled})
    })
  }
  return {transfer,projectAccess,isBusy:()=>busy}
}
module.exports={createMemoryFileControls,readBackup,writeBackup,MAX_BYTES}
