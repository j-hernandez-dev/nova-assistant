import {useEffect,useRef,useState} from 'react'
import type {DesktopSessionView} from '../shared/application'
import type {SourceFile,SourceImportResult} from '../shared/storage'
import {sameProjectPath} from './project_presentation'
import {usableSource} from './source_presentation'

/** Pending message selection is independent of source management and preview. */
export function usePromptSources(view:DesktopSessionView|null,workspace:string|null,locked:boolean,onImported:()=>void){
  const identity=JSON.stringify([view?.sessionId,view?.workspace])
  const [selection,setSelection]=useState<{identity:string;files:SourceFile[]}>({identity,files:[]})
  const [uploading,setUploading]=useState(false),[error,setError]=useState<string|null>(null),[imported,setImported]=useState(0)
  const [panelSignal,setPanelSignal]=useState({identity,revision:0})
  const flight=useRef(false),revision=useRef(0),alive=useRef(true),latest=useRef({identity,workspace,onImported})
  latest.current={identity,workspace,onImported}
  const refs=view?.knowledge?.attachmentRefs||[]
  const signature=JSON.stringify(refs.map(ref=>[ref.sourceId,ref.revisionId,ref.state]))
  const selected=selection.identity===identity?selection.files:[]
  const ready=!!workspace&&sameProjectPath(view?.workspace,workspace)&&!!view?.status.ready&&!!view.status.connected&&!view.recovering&&!view.gap
  const available=refs.filter(usableSource)
  const attachmentRefs=available.filter(ref=>selected.some(file=>file.id===ref.sourceId))
  const canSelect=ready&&!locked&&!uploading
  const canImport=canSelect&&!!view?.knowledge?.hostAcquisition
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;revision.current++}},[])
  useEffect(()=>{revision.current++;flight.current=false;setUploading(false);setSelection({identity,files:[]});setError(null);setImported(0)},[identity])
  useEffect(()=>{
    if(!ready)return
    // Only a new authoritative catalogue prunes selection. A newly imported
    // file may reach the picker receipt just before React receives its refs.
    setSelection(previous=>{
      if(previous.identity!==identity)return previous
      const files=previous.files.filter(file=>available.some(ref=>ref.sourceId===file.id)&&sameProjectPath(file.projectPath,workspace))
      return files.length===previous.files.length?previous:{identity,files}
    })
  },[identity,workspace,ready,signature])
  function choose(file:SourceFile,checked:boolean){
    if(!canSelect||!sameProjectPath(file.projectPath,workspace)||!available.some(ref=>ref.sourceId===file.id))return
    setSelection(previous=>{
      const files=previous.identity===identity?previous.files:[]
      return{identity,files:checked?(files.some(item=>item.id===file.id)?files:[...files,file]):files.filter(item=>item.id!==file.id)}
    })
  }
  function remove(id:string){setSelection(previous=>previous.identity===identity?{identity,files:previous.files.filter(file=>file.id!==id)}:previous)}
  function clear(){setSelection(previous=>previous.identity===identity?{identity,files:[]}:previous)}
  async function selectImported(result:SourceImportResult){
    if(!result.imported)return
    const captured=identity,root=workspace
    const current=()=>alive.current&&latest.current.identity===captured&&sameProjectPath(latest.current.workspace,root)
    if(!current())return
    setError(null);setImported(result.imported);latest.current.onImported()
    setPanelSignal(previous=>({identity:captured,revision:(previous.identity===captured?previous.revision:0)+1}))
    const ids=new Set(result.sourceIds||[])
    if(!ids.size)return
    try{
    let inventory:Awaited<ReturnType<typeof window.api.sourcesList>>|undefined
    for(let attempt=0;attempt<4;attempt++){
      inventory=await window.api.sourcesList()
      if(!current())return
      if(inventory.success||!['STORAGE_BUSY','PROJECT_BUSY','REVISION_CONFLICT','CONFLICT_ACTIVE_OPERATION'].includes(inventory.error?.code||''))break
      await new Promise(resolve=>setTimeout(resolve,80*2**attempt))
    }
    if(inventory?.success){
      const added=inventory.data.files.filter(file=>ids.has(file.id)&&sameProjectPath(file.projectPath,root)&&['READY','PARTIAL'].includes(file.state))
      setSelection(previous=>{const before=previous.identity===captured?previous.files:[];return{identity:captured,files:[...before,...added.filter(file=>!before.some(item=>item.id===file.id))]}})
    }else setError('SOURCE_SELECTION_UNAVAILABLE')
    }catch{if(current())setError('SOURCE_SELECTION_UNAVAILABLE')}
  }
  async function acquire(files?:File[]){
    if(!canImport||flight.current)return
    flight.current=true;const ticket=++revision.current,captured=identity,root=workspace
    const current=()=>alive.current&&ticket===revision.current&&latest.current.identity===captured&&sameProjectPath(latest.current.workspace,root)
    setUploading(true);setError(null);setImported(0)
    try{
      const result=await (files?window.api.sourcesDrop(files):window.api.sourcesPick())
      if(!current())return
      if(result.canceled)return result
      setImported(result.imported)
      await selectImported(result)
      if(!current())return
      if(!result.completed)setError(result.error?.code||'SOURCE_IMPORT_UNKNOWN')
      return result
    }catch{if(current())setError('SOURCE_IMPORT_UNKNOWN')}
    finally{if(current()){flight.current=false;setUploading(false)}}
  }
  return{selected,attachmentRefs,selectionReady:attachmentRefs.length===selected.length,panelRevision:panelSignal.identity===identity?panelSignal.revision:0,canSelect,canImport,uploading,error,imported,choose,remove,clear,acquire,selectImported}
}
