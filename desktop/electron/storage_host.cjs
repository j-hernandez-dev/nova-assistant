const fs = require('node:fs')
const path = require('node:path')
const os = require('node:os')
const crypto = require('node:crypto')

const CATEGORIES = Object.freeze(['chats','attachments','memories','navigation','configuration','audit','catalog','caches'])
const {CACHE_NAMES: CHROMIUM_CACHE_NAMES} = require('./chromium_cache.cjs')
const CACHE_NAMES = Object.freeze([...CHROMIUM_CACHE_NAMES,'.chromium-cache-backup'])
const PROFILE_SETTINGS = Object.freeze(['desktop-preferences.json','desktop-runtime-preferences.json','desktop-model-visibility.json','desktop-conversation-view.json','desktop-recovery.log','Preferences','Local State'])
const STATE_SETTINGS = Object.freeze(['desktop-context.json','embedding-preferences.json','memory-preferences.json','knowledge-preferences.json','web-preferences.json','fetch-preference.json','browser-preference.json','browser-search.json'])
const USAGE_FILES = Object.freeze(['model-usage.sqlite3','embedding-usage.sqlite3'])
const SQLITE_SUFFIXES = ['', '-wal','-shm','-journal']
const fail = code => ({success:false,error:{code}})
const canceled = () => ({success:false,canceled:true})
const key = value => process.platform === 'win32' ? value.toLowerCase() : value
const same = (a,b) => key(a) === key(b)
const inside = (root,target) => {const relative=path.relative(root,target);return !relative||(!path.isAbsolute(relative)&&relative!=='..'&&!relative.startsWith('..'+path.sep))}
const absolute = value => {if(typeof value!=='string'||!path.isAbsolute(value)||value.includes('\0'))throw Error('STORAGE_INVALID_PATH');return path.resolve(value)}

function configuredStateDir(home,filename) {
  try {
    safeAncestry(filename)
    const info=fs.lstatSync(filename)
    if(!info.isFile()||info.nlink!==1||info.size>10240)throw Error('STORAGE_STATE_CONFIG_UNAVAILABLE')
    const text=new TextDecoder('utf-8',{fatal:true}).decode(fs.readFileSync(filename))
    let value
    for(const original of text.split(/\r?\n/)){
      const line=original.trim(),split=line.indexOf('=')
      if(!line||line.startsWith('#')||split<0)continue
      if(line.slice(0,split).trim()==='state_dir')value=line.slice(split+1).trim()
    }
    if(value===undefined)return {stateDir:null,warnings:[]}
    if(value==='~')value=home
    else if(/^~[\\/]/.test(value))value=path.join(home,value.slice(2))
    if(!path.isAbsolute(value)||value.includes('\0'))throw Error('STORAGE_STATE_CONFIG_UNSUPPORTED')
    return {stateDir:absolute(value),warnings:[]}
  }catch(error){return {stateDir:null,warnings:error.code==='ENOENT'?[]:[error.message?.startsWith('STORAGE_')?error.message:'STORAGE_STATE_CONFIG_UNAVAILABLE']}}
}

function storageLocations(options) {
  const env=options.env||process.env,home=options.homeDir||os.homedir()
  const hostConfigFile=absolute(options.configFile||path.join(home,'.config','nova','config'))
  const config=options.stateDir?{stateDir:options.stateDir,warnings:[]}:configuredStateDir(home,hostConfigFile)
  const stateDir=absolute(config.stateDir||path.join(home,'.local','state','nova'))
  const usageDir=absolute(path.join(env.XDG_STATE_HOME||path.join(home,'.local','state'),'nova'))
  const usageFiles=USAGE_FILES.flatMap(name=>SQLITE_SUFFIXES.map(suffix=>path.join(usageDir,name+suffix)))
  const profileDir=absolute(options.profileDir)
  const auditDir=absolute(options.auditDir||(process.platform==='win32'
    ?path.join(env.LOCALAPPDATA||path.join(home,'AppData','Local'),'Nova','security_audit','v1')
    :path.join(env.XDG_STATE_HOME||path.join(home,'.local','state'),'nova','security_audit','v1')))
  const catalogDir=absolute(options.catalogDir||path.join(env.XDG_CACHE_HOME||path.join(home,'.cache'),'nova'))
  const browserProfiles=path.join(absolute(options.tempDir||os.tmpdir()),'nova-browser-profiles')
  const controlDir=absolute(options.controlDir||path.join(path.dirname(profileDir),'nova-storage-control'))
  if(inside(profileDir,controlDir)||inside(stateDir,controlDir)||inside(catalogDir,controlDir)||inside(auditDir,controlDir))throw Error('STORAGE_CONTROL_OVERLAP')
  const knowledge=path.join(stateDir,'knowledge','v1')
  const roots={profileDir,stateDir,auditDir,catalogDir,browserProfiles,controlDir,knowledge,usageDir,usageFiles,hostConfigFile,warnings:config.warnings}
  const caches=[...CACHE_NAMES.map(name=>path.join(profileDir,name)),path.join(knowledge,'cache'),path.join(knowledge,'staging')]
  const settings=[...PROFILE_SETTINGS.map(name=>path.join(profileDir,name)),...STATE_SETTINGS.map(name=>path.join(stateDir,name)),...usageFiles]
  const groups={
    chats:[path.join(stateDir,'projects'),path.join(stateDir,'sessions')],
    attachments:[path.join(knowledge,'blobs')],memories:[path.join(stateDir,'memory')],
    navigation:[path.join(stateDir,'browser-files'),browserProfiles],
    configuration:settings,audit:[auditDir],catalog:[catalogDir],caches,
  }
  const rootFingerprint=crypto.createHash('sha256').update(JSON.stringify(Object.entries(groups).map(([id,paths])=>[id,paths.map(key)]))).digest('hex')
  return {...roots,groups,rootFingerprint,manifest:path.join(controlDir,'pending-deletions.json')}
}

// Validate lexical ancestry before realpath can conceal a Windows junction.
// User project folders and original file locations never enter this allowlist.
function safeAncestry(target,{missing=true}={}) {
  const resolved=absolute(target),parts=[]
  let cursor=resolved
  for(;;){parts.push(cursor);const parent=path.dirname(cursor);if(parent===cursor)break;cursor=parent}
  for(const item of parts.reverse()) {
    let stat
    try{stat=fs.lstatSync(item)}catch(error){if(error.code==='ENOENT'&&missing)continue;throw error}
    if(stat.isSymbolicLink()||(!same(item,resolved)&&!stat.isDirectory()))throw Error('STORAGE_UNSAFE_PATH')
    // realpath differs for a reparse point even where isSymbolicLink is false.
    if(!same(path.resolve(fs.realpathSync.native(item)),item))throw Error('STORAGE_UNSAFE_PATH')
  }
  return resolved
}

function pendingState(locations) {
  try {
    safeAncestry(locations.manifest)
    const stat=fs.statSync(locations.manifest)
    if(!stat.isFile()||stat.nlink!==1||stat.size>16384)throw Error('STORAGE_PENDING_INVALID')
    const saved=JSON.parse(fs.readFileSync(locations.manifest,'utf8'))
    if(saved.schemaVersion!==1||!Array.isArray(saved.categories)||saved.categories.some(id=>!CATEGORIES.includes(id)||id==='attachments'))throw Error('STORAGE_PENDING_INVALID')
    if(saved.rootFingerprint!==locations.rootFingerprint)throw Error('STORAGE_ROOT_CHANGED')
    return {categories:[...new Set(saved.categories)],warnings:[]}
  }catch(error){return {categories:[],warnings:error.code==='ENOENT'?[]:[error.message==='STORAGE_ROOT_CHANGED'?'STORAGE_ROOT_CHANGED':'STORAGE_PENDING_INVALID']}}
}
function savePending(locations,categories) {
  safeAncestry(locations.controlDir);fs.mkdirSync(locations.controlDir,{recursive:true});safeAncestry(locations.controlDir)
  safeAncestry(locations.manifest)
  const temporary=path.join(locations.controlDir,`pending-${crypto.randomUUID()}.tmp`)
  let fd
  try{
    fd=fs.openSync(temporary,'wx',0o600)
    fs.writeFileSync(fd,JSON.stringify({schemaVersion:1,categories:[...new Set(categories)],rootFingerprint:locations.rootFingerprint,createdAt:new Date().toISOString()})+'\n')
    fs.fsyncSync(fd);fs.closeSync(fd);fd=undefined
    fs.renameSync(temporary,locations.manifest)
  }finally{if(fd!==undefined)fs.closeSync(fd);try{fs.unlinkSync(temporary)}catch{}}
}

function verifyTree(target) {
  safeAncestry(target)
  let stat
  try{stat=fs.lstatSync(target)}catch(error){if(error.code==='ENOENT')return;throw error}
  if(stat.isSymbolicLink()||(!stat.isDirectory()&&(!stat.isFile()||stat.nlink!==1)))throw Error('STORAGE_UNSAFE_PATH')
  if(stat.isDirectory())for(const name of fs.readdirSync(target))verifyTree(path.join(target,name))
}
function safeRemove(target) {
  safeAncestry(target)
  let stat
  try{stat=fs.lstatSync(target)}catch(error){if(error.code==='ENOENT')return;throw error}
  if(stat.isSymbolicLink())throw Error('STORAGE_UNSAFE_PATH')
  if(stat.isDirectory()) {
    for(const child of fs.readdirSync(target))safeRemove(path.join(target,child))
    safeAncestry(target,{missing:false});fs.rmdirSync(target)
  } else {
    if(!stat.isFile()||stat.nlink!==1)throw Error('STORAGE_UNSAFE_PATH')
    safeAncestry(target,{missing:false});fs.unlinkSync(target)
  }
}

// Called while the application holds its single-instance lock, before any
// SQLite store or Chromium profile is opened. Only category IDs are persisted.
function applyPendingStorageDeletions(options) {
  const locations=storageLocations(options),pending=pendingState(locations),completed=[],failed=[]
  for(const id of pending.categories) {
    try{for(const target of locations.groups[id])verifyTree(target);for(const target of locations.groups[id])safeRemove(target);completed.push(id)}
    catch(error){failed.push({id,code:error.code||error.message||'STORAGE_DELETE_FAILED'})}
  }
  if(pending.categories.length)savePending(locations,failed.map(item=>item.id))
  return {completed,failed,warnings:pending.warnings}
}

async function measureStorage(locations,report={}) {
  const totals=Object.fromEntries(CATEGORIES.map(id=>[id,0])),warnings=[...locations.warnings],seen=new Set(),folderBytes=Object.fromEntries(CATEGORIES.map(id=>[id,0])),exists={}
  // A configured state root can be an existing user directory. Scan only the
  // generated children, never arbitrary siblings beneath that shared root.
  const statePaths=[...locations.groups.chats,...locations.groups.memories,...locations.groups.navigation.slice(0,1),locations.knowledge,
    ...STATE_SETTINGS.map(name=>path.join(locations.stateDir,name))]
  const allRoots=[locations.profileDir,...statePaths,locations.auditDir,locations.catalogDir,locations.browserProfiles,locations.controlDir,...locations.usageFiles,locations.hostConfigFile]
    .sort((a,b)=>a.length-b.length).filter((item,index,items)=>!items.slice(0,index).some(parent=>inside(parent,item)))
  const cachePaths=locations.groups.caches
  const special=[...locations.groups.chats.map(root=>({root,id:'chats'})),...locations.groups.memories.map(root=>({root,id:'memories'})),
    ...locations.groups.navigation.map(root=>({root,id:'navigation'})),{root:locations.auditDir,id:'audit'},{root:locations.catalogDir,id:'catalog'},
    ...cachePaths.map(root=>({root,id:'caches'})),...locations.usageFiles.map(root=>({root,id:'configuration'})),{root:path.join(locations.knowledge,'blobs'),id:'attachments'}].sort((a,b)=>b.root.length-a.root.length)
  const queue=allRoots.map(root=>({target:root,root:true}))
  let active=0,entries=0
  await new Promise(resolve=>{
    function pump(){
      while(active<8&&queue.length){const entry=queue.shift();active++
        ;(async()=>{
          const target=entry.target
          try{
            if(++entries>250000)throw Error('STORAGE_SCAN_LIMIT')
            safeAncestry(target)
            const stat=await fs.promises.lstat(target)
            if(stat.isSymbolicLink())throw Error('STORAGE_UNSAFE_PATH')
            if(stat.isDirectory()) {
              for(const id of CATEGORIES)if(locations.groups[id].some(root=>same(target,root)))exists[id]=true
              if(same(target,locations.profileDir)||same(target,locations.stateDir))exists.configuration=true
              for(const name of await fs.promises.readdir(target))queue.push({target:path.join(target,name)})
            }else if(stat.isFile()){
              const identity=`${stat.dev}:${stat.ino}`
              if(seen.has(identity))return
              seen.add(identity)
              const category=special.find(item=>inside(item.root,target))?.id||'configuration'
              totals[category]+=stat.size
              for(const id of CATEGORIES)if(locations.groups[id].some(root=>inside(root,target))){folderBytes[id]+=stat.size;exists[id]=true}
            }else throw Error('STORAGE_UNSAFE_PATH')
          }catch(error){if(error.code!=='ENOENT')warnings.push(`${error.code||error.message||'STORAGE_SCAN_FAILED'}: ${target}`)}
        })().finally(()=>{active--;if(!active&&!queue.length)resolve();else pump()})
      }
      if(!active&&!queue.length)resolve()
    }pump()
  })
  // Blob bytes are counted once. Backend owns blob identities and tells us
  // which physical bytes are captured web pages rather than local attachments.
  if(Number.isSafeInteger(report.webSnapshotBytes)&&report.webSnapshotBytes>=0){
    const webBytes=Math.min(totals.attachments,report.webSnapshotBytes)
    totals.attachments-=webBytes;totals.navigation+=webBytes
    folderBytes.attachments=Math.max(0,folderBytes.attachments-webBytes)
  }
  if(Number.isSafeInteger(report.attachmentBytes)&&report.attachmentBytes>=0)folderBytes.attachments=Math.min(folderBytes.attachments,report.attachmentBytes)
  const folders=CATEGORIES.map(id=>({id,category:id,path:id==='configuration'?locations.profileDir:locations.groups[id][0],paths:id==='configuration'?[...new Set([locations.profileDir,locations.stateDir,locations.usageDir])]:locations.groups[id],bytes:folderBytes[id],exists:!!exists[id],restartRequired:id!=='attachments',complete:!warnings.length}))
  return {totalBytes:Object.values(totals).reduce((sum,value)=>sum+value,0),categories:CATEGORIES.map(id=>({id,bytes:totals[id],complete:!warnings.length})),folders,warnings}
}

function createStorageHost(options) {
  let locations=storageLocations(options)
  const {client,getProjects,confirm,openPath,restart}=options
  let busy=false,cached=null,cachedAt=0,inflight=null,generation=0,reportFlight=null,reportSignature='',sourceFlight=null
  const invalidate=()=>{generation++;cached=null;cachedAt=0;options.publish?.()}
  const projects=()=>{
    const value=getProjects(),list=Array.isArray(value)?value:value?.folders||[]
    return list.filter(item=>item&&typeof item.path==='string'&&path.isAbsolute(item.path)).map(item=>({path:path.resolve(item.path),name:typeof item.name==='string'?item.name:path.basename(item.path)}))
  }
  const ready=()=>!options.isBlocked?.()&&!options.externalBusy?.()&&!client.workspaceBusy?.()&&!client.view?.activeTurnId&&!client.view?.activeGenerationId&&!client.view?.recovering
  const normalizePath=(target,list)=>target===null?null:(typeof target==='string'&&list.find(item=>same(item.path,path.resolve(target)))?.path)
  function idsValid(ids){return Array.isArray(ids)&&ids.length>0&&ids.length<=1000&&new Set(ids).size===ids.length&&ids.every(id=>typeof id==='string'&&id.length>0&&id.length<=256)}
  async function backend(action,args){
    const result=await client.storage(action,args)
    if(result?.success===false||result?.completed===false||result?.accepted===false)throw Error(result.error?.code||'STORAGE_OPERATION_FAILED')
    return result?.data||result||{}
  }
  async function reportFor(list,sources=false){
    const signature=JSON.stringify([list,sources])
    if(reportFlight){const previous=reportFlight;if(reportSignature===signature)return previous;await previous.catch(()=>{})}
    reportSignature=signature
    const flight=backend(sources?'source_report':'report',{projects:list});reportFlight=flight
    try{
      const report=await flight
      // This path comes only from the trusted Python host composition. No
      // renderer argument or imported document can select a storage root.
      if(typeof report.roots?.stateDir==='string') {
        const reported=absolute(report.roots.stateDir)
        if(!same(reported,locations.stateDir)){locations=storageLocations({...options,stateDir:reported});cached=null;cachedAt=0}
      }
      return report
    }finally{if(reportFlight===flight)reportFlight=null}
  }
  function fileRecords(report,list,sources=false){
    const rows=sources?report.sources:report.files
    if(!Array.isArray(rows))throw Error('STORAGE_REPORT_INVALID')
    return rows.map(file=>({id:file.id,name:file.name,modifiedAt:file.modifiedAt,bytes:file.bytes,
      ...(sources?{kind:file.kind,url:file.url,state:file.state,downloadable:file.downloadable===true}:{}),
      projectPath:typeof file.projectPath==='string'?(list.find(item=>same(item.path,file.projectPath))?.path||null):null}))
  }
  function sourceContext(list){
    const sessionId=client.view?.sessionId,workspace=client.view?.workspace
    const projectPath=typeof workspace==='string'?normalizePath(workspace,list):undefined
    if(!sessionId||!projectPath)throw Error('STORAGE_PROJECT_UNAVAILABLE')
    return {projectPath,valid:()=>client.view?.sessionId===sessionId&&typeof client.view?.workspace==='string'&&same(client.view.workspace,projectPath)}
  }
  async function sourceSelection(ids,list){
    const context=sourceContext(list),report=await reportFor(list,true)
    const records=fileRecords(report,list,true).filter(file=>file.projectPath===context.projectPath)
    if(!context.valid()||ids.some(id=>!records.some(file=>file.id===id)))throw Error('STORAGE_INVALID_SELECTION')
    return {...context,records}
  }
  async function snapshot(force=false){
    const list=projects(),signature=JSON.stringify(list)
    if(!force&&cached&&cached.signature===signature&&Date.now()-cachedAt<5000)return cached.data
    if(inflight){const start=generation;const data=await inflight;return !force&&start===generation&&cached?.signature===signature?data:snapshot(true)}
    const started=generation
    inflight=(async()=>{
      const report=await reportFor(list),files=fileRecords(report,list)
      const measured=await measureStorage(locations,report),pending=pendingState(locations)
      const grouped=[{path:null,name:''},...list].map(project=>{
        const selected=files.filter(file=>file.projectPath===project.path)
        return {...project,bytes:selected.reduce((sum,item)=>sum+item.bytes,0),fileCount:selected.length}
      })
      const data={...measured,projects:grouped,restartRequired:!!pending.categories.length,warnings:[...measured.warnings,...pending.warnings]}
      if(started!==generation)return null
      cached={signature,data};cachedAt=Date.now();return data
    })().finally(()=>{inflight=null})
    const data=await inflight
    return data===null?snapshot(true):data
  }
  async function mutate(work){
    if(busy||!ready())return fail('STORAGE_BUSY')
    busy=true
    try{return await work(()=>ready())}catch(error){return fail(error.message||error.code||'STORAGE_OPERATION_FAILED')}finally{busy=false}
  }
  async function confirmation(kind,extra,validate){
    const answer=await confirm({kind,...extra,validate})
    return (answer===true||answer?.confirmed===true)&&validate()
  }
  return {
    async overview(args={}){try{return {success:true,data:await snapshot(args?.refresh===true)}}catch(error){return fail(error.message||'STORAGE_SCAN_FAILED')}},
    async files(target){
      try{const list=projects(),projectPath=normalizePath(target,list);if(projectPath===undefined)return fail('STORAGE_PROJECT_UNAVAILABLE')
        const report=await reportFor(list);return {success:true,data:{projectPath,files:fileRecords(report,list).filter(file=>file.projectPath===projectPath)}}
      }catch(error){return fail(error.message||'STORAGE_OPERATION_FAILED')}
    },
    async sources(){
      try{
        const list=projects(),context=sourceContext(list)
        const signature=JSON.stringify([client.view.sessionId,context.projectPath,list])
        // Share this read before checking workspaceBusy: its own pending
        // backend report makes the workspace busy until the reply arrives.
        if(sourceFlight?.signature===signature)return await sourceFlight.promise
        if(busy||!ready())return fail('STORAGE_BUSY')
        const promise=(async()=>{
          const report=await reportFor(list,true)
          if(!context.valid())return fail('STORAGE_PROJECT_UNAVAILABLE')
          return {success:true,data:{files:fileRecords(report,list,true).filter(file=>file.projectPath===context.projectPath),projects:list}}
        })()
        sourceFlight={signature,promise}
        try{return await promise}finally{if(sourceFlight?.promise===promise)sourceFlight=null}
      }catch(error){return fail(error.message||'STORAGE_OPERATION_FAILED')}
    },
    async sourcePreview(id){return mutate(async valid=>{
      if(!idsValid([id]))return fail('STORAGE_INVALID_SELECTION')
      const list=projects(),selection=await sourceSelection([id],list)
      if(!valid()||!selection.valid())return fail('STORAGE_BUSY')
      const data=await backend('source_preview',{ids:[id],projects:list})
      if(!selection.valid()||data.preview?.sourceId!==id)return fail('STORAGE_PROJECT_UNAVAILABLE')
      return {success:true,data:{...data.preview,root:selection.projectPath}}
    })},
    async move(ids,target,sources=false){return mutate(async valid=>{
      const list=projects(),projectPath=normalizePath(target,list)
      if(!idsValid(ids)||projectPath===undefined)return fail('STORAGE_INVALID_SELECTION')
      const selection=sources?await sourceSelection(ids,list):null
      if(!valid()||selection&&!selection.valid())return fail('STORAGE_BUSY')
      const data=await backend(sources?'source_move':'move',{ids,projectPath,projects:list});invalidate();return {success:true,data}
    })},
    async deleteFiles(ids,sources=false){return mutate(async valid=>{
      if(!idsValid(ids))return fail('STORAGE_INVALID_SELECTION')
      const list=projects(),selection=sources?await sourceSelection(ids,list):null
      const current=()=>valid()&&(!selection||selection.valid())
      if(!await confirmation(sources?'sources-delete-files':'storage-delete-files',{fileCount:ids.length},current))return canceled()
      const data=await backend(sources?'source_delete':'delete',{ids,projects:list});invalidate();return {success:true,data}
    })},
    async download(ids,sources=false){return mutate(async valid=>{
      if(!idsValid(ids)||typeof options.pickSave!=='function')return fail('STORAGE_INVALID_SELECTION')
      const list=projects(),selection=sources?await sourceSelection(ids,list):null
      const records=selection?selection.records:fileRecords(await reportFor(list),list)
      const selected=ids.map(id=>records.find(file=>file.id===id))
      if(selected.some(file=>!file||sources&&!file.downloadable))return fail('STORAGE_INVALID_SELECTION')
      let downloaded=0
      for(const file of selected){
        if(!valid()||selection&&!selection.valid())return fail('STORAGE_BUSY')
        const name=path.basename(file.name).replace(/[<>:"/\\|?*\x00-\x1f]/g,'_')||'download'
        const picked=await options.pickSave({name})
        if(picked.canceled||typeof picked.filePath!=='string')return downloaded?{success:true,data:{downloaded}}:canceled()
        const destination=absolute(picked.filePath)
        if([locations.profileDir,locations.stateDir,locations.auditDir,locations.catalogDir,locations.controlDir,locations.browserProfiles].some(root=>inside(root,destination)))return fail('STORAGE_PROTECTED_DESTINATION')
        if(!valid()||selection&&!selection.valid())return fail('STORAGE_BUSY')
        await backend(sources?'source_export':'export',{ids:[file.id],path:destination,projects:list});downloaded++
      }
      return {success:true,data:{downloaded}}
    })},
    async openFolder(id){
      if(!CATEGORIES.includes(id))return fail('STORAGE_UNKNOWN_FOLDER')
      try{
        const targets=id==='configuration'?[locations.profileDir,locations.stateDir]:locations.groups[id]
        for(const target of targets){safeAncestry(target);try{if(fs.statSync(target).isDirectory()){const error=await openPath(target);return error?fail('STORAGE_OPEN_FAILED'):{success:true,data:{path:target}}}}catch(error){if(error.code!=='ENOENT')throw error}}
        return fail('STORAGE_FOLDER_NOT_FOUND')
      }catch{return fail('STORAGE_OPEN_FAILED')}
    },
    async deleteFolder(id){return mutate(async valid=>{
      if(!CATEGORIES.includes(id))return fail('STORAGE_UNKNOWN_FOLDER')
      await reportFor(projects())
      const target=id==='configuration'?locations.profileDir:locations.groups[id][0]
      if(!await confirmation('storage-delete-folder',{folderId:id,path:target,restartRequired:id!=='attachments'},valid))return canceled()
      if(id==='attachments')await backend('delete_all',{projects:projects()})
      else{const pending=pendingState(locations);if(pending.warnings.length)return fail('STORAGE_PENDING_INVALID');savePending(locations,[...pending.categories,id])}
      invalidate();return {success:true,data:{restartRequired:id!=='attachments',queued:id!=='attachments'}}
    })},
    async restart(){return mutate(async valid=>{
      if(!await confirmation('storage-restart',{},valid))return canceled()
      await restart();return {success:true,data:{restartRequired:false}}
    })},
    async detachProject(target,deleteFiles=false){return mutate(async valid=>{
      if(typeof target!=='string'||!path.isAbsolute(target)||typeof deleteFiles!=='boolean')return fail('STORAGE_INVALID_SELECTION')
      const projectPath=path.resolve(target)
      if(!valid())return fail('STORAGE_BUSY')
      const data=await backend(deleteFiles?'delete_project':'detach_project',{projectPath,projects:projects()});invalidate();return {success:true,data}
    })},
    invalidate,
    isBusy:()=>busy||!!reportFlight||!!options.externalBusy?.(),
  }
}
module.exports={createStorageHost,applyPendingStorageDeletions,measureStorage,storageLocations,resolveStorageLocations:storageLocations,CATEGORIES}
