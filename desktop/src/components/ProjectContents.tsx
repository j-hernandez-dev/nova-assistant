import {useEffect,useId,useRef,useState,type ReactNode} from 'react'
import type {DesktopSessionView,MemoryControlResult} from '../../shared/application'
import type {SourceFile} from '../../shared/storage'
import {useI18n} from '../i18n'
import {sameProjectPath} from '../project_presentation'
import {sourceIcon,usableSource} from '../source_presentation'
import {memoryInspection,type MemoryInspection} from './MemoryRecords'
import {NovaIcon} from './NovaIcon'
import '../project_contents.css'

type Tab='files'|'sources'|'memories'
type Props={rootDir:string;view:DesktopSessionView|null;busy:boolean;children:ReactNode;refreshKey?:number;sourcePanelRevision?:number;selectedSourceIds?:string[];onSourceChoose?:(source:SourceFile,checked:boolean)=>void;onSourceSelect:(source:SourceFile)=>void;onMemorySelect:(record:MemoryInspection)=>void;onPreviewClear:()=>void}
const transient=(code?:string)=>['STORAGE_BUSY','PROJECT_BUSY','REVISION_CONFLICT','CONFLICT_ACTIVE_OPERATION','MEMORY_BUSY','MEMORY_MAINTENANCE_BUSY'].includes(code||'')
const mask=(record:MemoryInspection):MemoryInspection=>record.sensitivityClass==='SENSITIVE'?{...record,canonicalText:'[SENSITIVE — explicit inspection required]',hidden:true}:record
export function ProjectContents({rootDir,view,busy,children,refreshKey,sourcePanelRevision=0,selectedSourceIds=[],onSourceChoose,onSourceSelect,onMemorySelect,onPreviewClear}:Props){
  const {t}=useI18n(),id=useId()
  const [tab,setTab]=useState<Tab>('files'),[sources,setSources]=useState<SourceFile[]|null>(null),[records,setRecords]=useState<MemoryInspection[]|null>(null)
  const [cursor,setCursor]=useState<string|null>(null),[reveal,setReveal]=useState(false),[loading,setLoading]=useState(false),[error,setError]=useState<string|null>(null)
  const alive=useRef(true),epoch=useRef(0),activeTab=useRef(tab),root=useRef(rootDir)
  activeTab.current=tab;root.current=rootDir
  const ready=!busy&&!!view?.status.ready&&!!view.status.connected&&!view.recovering&&!view.gap&&!view.activeTurnId&&!view.activeGenerationId&&!view.memory?.maintenanceBusy&&sameProjectPath(view.workspace,rootDir)
  const sourceSignature=tab==='sources'?JSON.stringify(view?.knowledge?.attachmentRefs?.map(item=>[item.sourceId,item.revisionId,item.state])||[]):''
  const clearPreview=useRef(onPreviewClear);clearPreview.current=onPreviewClear
  const requestedSnapshot=useRef('')
  useEffect(()=>{if(sourcePanelRevision)changeTab('sources')},[sourcePanelRevision])
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;epoch.current++;clearPreview.current()}},[])
  function begin(target:Tab){const token=++epoch.current;setLoading(true);setError(null);return()=>alive.current&&token===epoch.current&&root.current===rootDir&&activeTab.current===target}
  async function loadSources(){
    if(!ready)return
    const current=begin('sources')
    try{
      for(let attempt=0;attempt<6;attempt++){
        const result=await window.api.sourcesList()
        if(!current())return
        if(result.success){setSources(result.data.files.filter(file=>sameProjectPath(file.projectPath,rootDir)));return}
        const code=result.error?.code||'STORAGE_UNAVAILABLE'
        if(!transient(code)||attempt===5){setError(code);return}
        await new Promise(resolve=>setTimeout(resolve,Math.min(80*2**attempt,400)))
        if(!current())return
      }
    }catch{if(current())setError('STORAGE_UNAVAILABLE')}
    finally{if(current())setLoading(false)}
  }
  async function loadMemories(includeSensitive=false,next?:string){
    if(!ready||!view?.memory)return
    const current=begin('memories')
    try{
      let result:MemoryControlResult|undefined
      for(let attempt=0;attempt<4;attempt++){
        result=await window.api.memoryCommand('memory_list',{scope:'WORKSPACE',limit:20,includeSensitive,...(next?{cursor:next}:{})})
        if(!current())return
        if(result.canceled)return
        if(result.completed){
          const rows=(Array.isArray(result.data?.records)?result.data.records:[]).map(memoryInspection).filter((row:MemoryInspection|null):row is MemoryInspection=>!!row&&row.scopeKind==='WORKSPACE')
          setRecords(old=>next?[...(old||[]),...rows.filter((row:MemoryInspection)=>!old?.some(item=>item.memoryId===row.memoryId))]:rows)
          setCursor(typeof result.data?.nextCursor==='string'?result.data.nextCursor:null);setReveal(includeSensitive);return
        }
        const code=result.error?.code||'MEMORY_UNAVAILABLE'
        // Sensitive inspection retains exactly one host confirmation/request.
        if(includeSensitive||!transient(code)||attempt===3){setError(code);return}
        await new Promise(resolve=>setTimeout(resolve,80*2**attempt))
        if(!current())return
      }
    }catch{if(current())setError('MEMORY_UNAVAILABLE')}
    finally{if(current())setLoading(false)}
  }
  useEffect(()=>{
    if(!ready||tab==='files')return
    // A read temporarily marks the backend busy. Its completion must not
    // schedule the same read again when readiness returns.
    const snapshot=JSON.stringify([rootDir,tab,sourceSignature,refreshKey])
    if(requestedSnapshot.current===snapshot)return
    const timer=setTimeout(()=>{
      requestedSnapshot.current=snapshot
      if(tab==='sources')void loadSources()
      else {if(reveal){setReveal(false);setRecords(old=>old?.map(mask)||null);onPreviewClear()}void loadMemories(false)}
    },0)
    return()=>clearTimeout(timer)
  },[tab,rootDir,ready,sourceSignature,refreshKey])
  function changeTab(next:Tab){
    if(next===tab)return
    requestedSnapshot.current=''
    epoch.current++;setLoading(false);setError(null);setReveal(false);setRecords(old=>old?.map(mask)||null)
    onPreviewClear();setTab(next)
  }
  const tabs=[['files','projectFilesTab'],['sources','projectSourcesTab'],['memories','projectMemoriesTab']] as const
  return <section className="project-content-panel" aria-label={t('projectContents')}>
    <div className="project-content-tabs" role="tablist" aria-label={t('projectContents')}>
      {tabs.map(([value,label],index)=><button key={value} type="button" role="tab" id={id+'-'+value} aria-controls={id+'-pane-'+value} aria-selected={tab===value} tabIndex={tab===value?0:-1} onClick={()=>changeTab(value)}
        onKeyDown={event=>{let next=index;if(event.key==='ArrowRight')next=(index+1)%tabs.length;else if(event.key==='ArrowLeft')next=(index+tabs.length-1)%tabs.length;else if(event.key==='Home')next=0;else if(event.key==='End')next=tabs.length-1;else return;event.preventDefault();changeTab(tabs[next][0]);document.getElementById(id+'-'+tabs[next][0])?.focus()}}>{t(label)}</button>)}
    </div>
    <div className="project-content-pane" role="tabpanel" id={id+'-pane-files'} aria-labelledby={id+'-files'} hidden={tab!=='files'}>{children}</div>
    {tab!=='files'&&<div className="project-content-pane" role="tabpanel" id={id+'-pane-'+tab} aria-labelledby={id+'-'+tab}>
      {tab==='memories'&&<label className="project-content-sensitive"><input type="checkbox" checked={reveal} disabled={!ready||loading||!view?.memory} onChange={event=>{
        const next=event.target.checked
        if(!next){setReveal(false);setRecords(old=>old?.map(mask)||null);onPreviewClear()}
        void loadMemories(next)
      }}/><span>{t('memoriesShowSensitive')}</span></label>}
      <div className="project-content-list" aria-busy={loading}>
        {!ready&&<p className="explorer-loading" role="status">{t('projectContentsWaiting')}</p>}
        {loading&&<p className="explorer-loading" role="status">{t('projectContentsLoading')}</p>}
        {error&&<div className="explorer-error" role="alert"><p>{t(transient(error)?'projectContentsWaiting':'projectContentsFailed')}</p><details><summary>{t('diagnosticDetails')}</summary><code>{error}</code></details>
          <button className="explorer-show-more" disabled={!ready||loading} onClick={()=>tab==='sources'?void loadSources():void loadMemories(reveal)}>{t('projectContentsRetry')}</button></div>}
        {tab==='sources'?sources?.map(source=>{
          const eligible=!!onSourceChoose&&!!view?.knowledge?.attachmentRefs.some(ref=>ref.sourceId===source.id&&usableSource(ref))
          return <div className="project-source-row" data-selected={selectedSourceIds.includes(source.id)||undefined} key={source.id}>
            <input type="checkbox" checked={selectedSourceIds.includes(source.id)} disabled={!ready||loading||!eligible} aria-label={`${t('promptSourceSelect')}: ${source.name}`} title={t(eligible?'promptSourceSelect':'promptSourceUnavailable')} onChange={event=>onSourceChoose?.(source,event.target.checked)}/>
            <button type="button" className="project-content-item" disabled={!ready||loading} title={source.url||source.name} onClick={()=>onSourceSelect(source)}><NovaIcon name={sourceIcon(source)} size={16}/><span>{source.name}</span></button>
          </div>
        }):records?.map(record=><button type="button" className="project-content-item" key={record.memoryId} disabled={!ready||loading} title={record.hidden?t('memorySettingsHidden'):record.canonicalText} onClick={()=>onMemorySelect(record)}><NovaIcon name="memories" size={16}/><span>{record.hidden?t('memorySettingsHidden'):record.canonicalText}</span></button>)}
        {!loading&&!error&&ready&&(tab==='sources'?sources?.length===0:records?.length===0)&&<p className="explorer-empty-dir">{t(tab==='sources'?'projectSourcesEmpty':'projectMemoriesEmpty')}</p>}
        {tab==='memories'&&cursor&&<button type="button" className="explorer-show-more" disabled={!ready||loading} onClick={()=>void loadMemories(reveal,cursor)}>{t('memoriesLoadMore')}</button>}
      </div>
    </div>}
  </section>
}
