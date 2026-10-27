import {useCallback,useEffect,useId,useRef,useState} from 'react'
import type {DesktopSessionView} from '../../shared/application'
import type {SourceFile,SourceInventory,SourceImportResult,StorageResult} from '../../shared/storage'
import {useI18n,type TranslationKey} from '../i18n'
import {fileBasename} from '../project_presentation'
import {storageBytes} from '../storage_presentation'
import {sourceIcon} from '../source_presentation'
import {ModalHost} from './ModalHost'
import {SettingsSelect} from './SettingsSelect'
import {NovaIcon} from './NovaIcon'
import {DataActionDock} from './DataActionDock'
import '../memories.css'
import '../data_table.css'
import '../sources.css'

type Props={view:DesktopSessionView|null;open?:boolean;locked?:boolean;projectRevision?:string;onAcquire?:(files?:File[])=>Promise<SourceImportResult|undefined>;onImported?:(result:SourceImportResult)=>Promise<void>;onClose:()=>void}
const transientSourceRead=(code:string|null)=>!!code&&['STORAGE_BUSY','PROJECT_BUSY','CONFLICT_ACTIVE_OPERATION','REVISION_CONFLICT'].includes(code)
export function SourcesWindow({view,open=true,locked=false,projectRevision='',onAcquire,onImported,onClose}:Props){
  const {t,locale}=useI18n(),id=useId()
  const [tab,setTab]=useState<'saved'|'add'>('saved'),[query,setQuery]=useState(''),[filter,setFilter]=useState(''),[url,setUrl]=useState('')
  const [inventory,setInventory]=useState<SourceInventory>({files:[],projects:[]}),[selected,setSelected]=useState<string[]>([])
  const [loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[dragging,setDragging]=useState(false)
  const [loaded,setLoaded]=useState(false),[loadError,setLoadError]=useState<string|null>(null)
  const [error,setError]=useState<string|null>(null),[notice,setNotice]=useState<TranslationKey|null>(null),[imported,setImported]=useState(0)
  const [pendingUrl,setPendingUrl]=useState<string|null>(null)
  const alive=useRef(true),enabled=useRef(open),epoch=useRef(0),operation=useRef(false)
  const readFlight=useRef<ReturnType<typeof window.api.sourcesList>|null>(null)
  enabled.current=open
  const ready=!!view?.workspace&&!!view.status.ready&&!view.recovering&&!view.gap
  const running=!!view?.knowledgeOperations?.some(item=>item.status==='running')
  const terminal=JSON.stringify(view?.knowledgeOperations?.filter(item=>item.status!=='running').map(item=>[item.operationId,item.status])||[])
  const blocked=locked||busy||running||!!pendingUrl||!ready||!!view?.activeTurnId||!!view?.activeGenerationId
  const disabled=blocked||loading||!!loadError
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;epoch.current++}},[])
  const select=useCallback((ids:string[])=>setSelected(ids),[])
  const close=()=>{setSelected([]);onClose()}
  const load=useCallback(async()=>{
    const request=++epoch.current;setLoading(true);setLoadError(null)
    const current=()=>alive.current&&enabled.current&&request===epoch.current
    try{
      for(let attempt=0;attempt<6;attempt++){
        // StrictMode replays mount effects in development. Each observer keeps
        // its own epoch while both await the same read, never duplicate writes.
        const flight=readFlight.current||(readFlight.current=window.api.sourcesList())
        let result:Awaited<typeof flight>
        try{result=await flight}finally{if(readFlight.current===flight)readFlight.current=null}
        if(!current())return
        if(result.success){setInventory(result.data);setLoaded(true);setLoadError(null);setSelected(previous=>previous.filter(value=>result.data.files.some(file=>file.id===value)));return}
        if(result.canceled)return
        const code=result.error?.code||'STORAGE_UNAVAILABLE'
        if(!transientSourceRead(code)||attempt===5){setLoadError(code);return}
        // Only inventory reads may wait for transient host work. Mutations
        // continue to require one explicit request and their original receipt.
        await new Promise(resolve=>setTimeout(resolve,Math.min(80*2**attempt,400)))
        if(!current())return
      }
    }catch{if(current())setLoadError('STORAGE_UNAVAILABLE')}
    finally{if(current())setLoading(false)}
  },[])
  useEffect(()=>{
    if(!open){epoch.current++;setSelected([]);return}
    if(ready&&!running&&!operation.current)void load()
    else if(!ready)setLoading(false)
  },[open,ready,running,terminal,projectRevision,load])
  useEffect(()=>{
    if(!pendingUrl)return
    const result=view?.knowledgeOperations?.find(item=>item.operationId===pendingUrl)
    if(!result||result.status==='running')return
    setPendingUrl(null)
    if(result.status==='completed'&&!result.result?.error){setUrl('');setNotice('sourcesImported');setImported(1);setTab('saved');setQuery('');setFilter('');if(result.result?.sourceId)void onImported?.({completed:true,imported:1,sourceIds:[result.result.sourceId]}).catch(()=>{})}
    else setError(result.result?.error?.code||'SOURCE_IMPORT_FAILED')
  },[pendingUrl,terminal])
  const text=(value:string)=>value.normalize('NFD').replace(/\p{M}/gu,'').toLocaleLowerCase(locale)
  const files=inventory.files.filter(file=>text(file.name+' '+(file.url||'')).includes(text(filter)))
  const ids=selected.filter(value=>files.some(file=>file.id===value)),all=files.length>0&&ids.length===files.length
  const downloadable=ids.every(value=>files.find(file=>file.id===value)?.downloadable)
  const number=new Intl.NumberFormat(locale)
  const modified=(value:string)=>{const date=new Date(value);return Number.isNaN(date.getTime())?t('storageUnknownDate'):new Intl.DateTimeFormat(locale,{dateStyle:'medium',timeStyle:'short'}).format(date)}
  function search(){setFilter(query);select(selected.filter(value=>inventory.files.some(file=>file.id===value&&text(file.name+' '+(file.url||'')).includes(text(query)))))}
  async function refresh(){if(blocked||loading)return;setError(null);setNotice(null);await load()}
  async function mutate(request:()=>Promise<StorageResult>,done:TranslationKey,reload=true){
    if(disabled||operation.current)return
    operation.current=true;setBusy(true);setError(null);setNotice(null)
    try{
      const result=await request()
      if(!alive.current)return
      if(result.canceled)return
      if(!result.success){setError(result.error?.code||'STORAGE_FAILED');return}
      setNotice(done)
      if(reload){select([]);await load()}
    }catch{if(alive.current)setError('STORAGE_OUTCOME_UNKNOWN')}
    finally{operation.current=false;if(alive.current)setBusy(false)}
  }
  async function acquire(dropped?:File[]){
    if(disabled||operation.current||!view?.knowledge?.hostAcquisition)return
    operation.current=true;setBusy(true);setError(null);setNotice(null);setImported(0)
    try{
      const result=await (onAcquire?onAcquire(dropped):dropped?window.api.sourcesDrop(dropped):window.api.sourcesPick())
      if(!result)return
      if(!onAcquire&&result.imported)await onImported?.(result)
      if(!alive.current)return
      setImported(result.imported)
      if(result.canceled)return
      if(result.completed){setNotice('sourcesImported');setTab('saved');setQuery('');setFilter('')}
      else setError(result.error?.code||'SOURCE_IMPORT_UNKNOWN')
      await load()
    }catch{if(alive.current)setError('SOURCE_IMPORT_UNKNOWN')}
    finally{operation.current=false;if(alive.current)setBusy(false)}
  }
  async function importUrl(){
    if(disabled||operation.current||!url.trim()||!view?.knowledge?.hostAcquisition)return
    operation.current=true;setBusy(true);setError(null);setNotice(null);setImported(0)
    try{
      const receipt=await window.api.knowledgeCommand('source_import_url',{url:url.trim(),scope:'WORKSPACE'})
      if(!alive.current)return
      if(receipt.accepted&&receipt.createdIds.operationId)setPendingUrl(receipt.createdIds.operationId)
      else setError(receipt.error?.code||'SOURCE_IMPORT_UNKNOWN')
    }catch{if(alive.current)setError('SOURCE_IMPORT_UNKNOWN')}
    finally{operation.current=false;if(alive.current)setBusy(false)}
  }
  function sourceName(file:SourceFile){return <><NovaIcon name={sourceIcon(file)} size={18}/><span>{file.name}{file.kind==='url'&&<small>{file.url}</small>}{!file.downloadable&&<small>{t('sourcesNoContent')}</small>}</span></>}
  return <ModalHost open={open} onClose={close} labelledBy={id} className="nova-memories-dialog nova-sources-dialog nova-surface-dialog">
    <header className="memories-header nova-surface-header"><div><span className="nova-settings-eyebrow">Nova</span><h1 id={id}>{t('sources')}</h1></div>
      <button type="button" className="nova-dismiss-button memories-close" aria-label={t('closeDialog')} onClick={close}><NovaIcon name="close" size={20}/></button></header>
    <div className="memories-project" title={view?.workspace||undefined}><NovaIcon name="folder" size={16}/><span>{t('memoriesCurrentProject')}</span><strong>{fileBasename(view?.workspace||'')||t('settingsUnknown')}</strong></div>
    <div className="memories-tabs" role="tablist" aria-label={t('sources')}>
      {(['saved','add'] as const).map(value=><button key={value} id={id+'-'+value} type="button" role="tab" aria-selected={tab===value} aria-controls={id+'-content'} disabled={busy} onClick={()=>setTab(value)}>{t(value==='saved'?'sourcesSaved':'sourcesAdd')}</button>)}
    </div>
    <div className="sources-content" id={id+'-content'} role="tabpanel" aria-labelledby={id+'-'+tab} data-view={tab}>
      {loadError&&<div className={'settings-feedback'+(transientSourceRead(loadError)?'':' error')} role={transientSourceRead(loadError)?'status':'alert'}>
        <p>{t(transientSourceRead(loadError)?'sourcesBusy':'sourcesLoadFailed')}</p>
        <details><summary>{t('diagnosticDetails')}</summary><code>{loadError}</code></details></div>}
      {error&&<div className="settings-feedback error" role="alert"><p>{t(error.includes('UNKNOWN')?'sourcesUnknown':error==='STORAGE_UNAVAILABLE'?'sourcesUnavailable':'sourcesError')}</p>
        {imported>0&&<p>{t('sourcesPartialImport')}: {number.format(imported)}</p>}<details><summary>{t('diagnosticDetails')}</summary><code>{error}</code></details></div>}
      {notice&&<p className="memories-feedback" role="status">{t(notice)}{notice==='sourcesImported'?`: ${number.format(imported)}`:''}</p>}
      {!ready&&<p className="memories-notice" role="status">{t('sourcesUnavailable')}</p>}
      {(busy||pendingUrl)&&<p className="sources-progress" role="status">{t(tab==='add'||pendingUrl?'sourcesWorking':'settingsServiceSaving')}</p>}
      {tab==='saved'?<>
        <form className="nova-data-search" role="search" onSubmit={event=>{event.preventDefault();search()}}><NovaIcon name="search" size={17}/>
          <input type="search" aria-label={t('sourcesSearch')} placeholder={t('sourcesSearch')} value={query} onChange={event=>setQuery(event.target.value)}/>
          <button type="submit" className="nova-search-submit" disabled={busy} aria-label={t('sourcesSearchSubmit')}><NovaIcon name="forward" size={18}/></button>
          <button type="button" className="nova-search-refresh" disabled={blocked||loading} aria-label={t('sourcesRefresh')} title={t('sourcesRefresh')} onClick={()=>void refresh()}><NovaIcon name="sync" size={17}/></button></form>
        <div className="sources-summary"><span>{loaded?<>{number.format(files.length)} {t(files.length===1?'sourcesCountOne':'sourcesCount')}</>:loading?null:t('sourcesCountUnavailable')}</span><span role="status">{loading?t('sourcesLoading'):null}</span></div>
        <div className="nova-data-region sources-saved-region">
        <div className="nova-data-scroll sources-scroll"><div className="nova-data-table-wrap"><table className="nova-data-table sources-table" aria-busy={loading}>
          <thead><tr><th className="sources-check"><input type="checkbox" aria-label={t('sourcesSelectAll')} checked={all} disabled={disabled||!files.length} ref={element=>{if(element)element.indeterminate=ids.length>0&&!all}} onChange={event=>select(event.target.checked?files.map(file=>file.id):[])}/></th>
            <th scope="col">{t('sourcesName')}</th><th scope="col">{t('storageModified')}</th><th scope="col">{t('storageSize')}</th></tr></thead>
          <tbody>{files.map(file=><tr key={file.id} data-selected={ids.includes(file.id)||undefined}><td className="sources-check"><input id={id+'-'+file.id} type="checkbox" aria-label={`${t('sourcesSelect')}: ${file.name}`} checked={ids.includes(file.id)} disabled={disabled} onChange={event=>select(event.target.checked?[...ids,file.id]:ids.filter(value=>value!==file.id))}/></td>
            <td><label className="sources-name" htmlFor={id+'-'+file.id} title={file.url||file.name}>{sourceName(file)}</label></td><td><time dateTime={file.modifiedAt}>{modified(file.modifiedAt)}</time></td><td>{storageBytes(file.bytes,locale)}</td></tr>)}</tbody></table>
          {!files.length&&<div className="memories-empty" role="status"><NovaIcon name="search" size={30}/><h3>{t(loading?'sourcesLoading':loadError?transientSourceRead(loadError)?'sourcesWaiting':'sourcesLoadFailed':!ready?'sourcesUnavailable':filter?'sourcesNoMatches':'sourcesEmpty')}</h3>{!loading&&<p>{t(loadError?'sourcesRetryHint':!ready?'sourcesRetryHint':filter?'sourcesNoMatchesHint':'sourcesEmptyHint')}</p>}</div>}</div></div>
        <DataActionDock className="sources-actions" visible={ids.length>0}>
          <span className="nova-data-selection-count">{number.format(ids.length)} {t(ids.length===1?'sourcesSelectedOne':'sourcesSelected')}</span>
          <SettingsSelect value={view?.workspace||''} disabled={disabled||!ids.length} aria-label={t('storageLink')} options={[{value:'',label:t('storageUnlink')},...inventory.projects.map(project=>({value:project.path,label:project.name,description:inventory.projects.filter(other=>other.name===project.name).length>1?project.path:undefined}))]}
            onChange={target=>void mutate(()=>window.api.sourcesMove(ids,target||null),'sourcesMoveDone')}/>
          <button type="button" className="nova-settings-secondary memories-button" disabled={disabled||!ids.length||!downloadable} onClick={()=>void mutate(()=>window.api.sourcesDownload(ids),'sourcesDownloadDone',false)}>{t('storageDownload')}</button>
          <button type="button" className="nova-settings-danger" disabled={disabled||!ids.length} onClick={()=>void mutate(()=>window.api.sourcesDelete(ids),'sourcesDeleteDone')}>{t('storageDelete')}</button>
        </DataActionDock>
        </div>
      </>:<div className="sources-add-scroll"><div className="sources-add">
        <button type="button" className="sources-dropzone" data-dragging={dragging||undefined} disabled={disabled||!view?.knowledge?.hostAcquisition} onClick={()=>void acquire()}
          onDragOver={event=>{event.preventDefault();if(!disabled){event.dataTransfer.dropEffect='copy';setDragging(true)}}} onDragLeave={()=>setDragging(false)}
          onDrop={event=>{event.preventDefault();setDragging(false);if(!disabled)void acquire(Array.from(event.dataTransfer.files))}}>
          <NovaIcon name="folder" size={44}/><strong>{t('sourcesDrop')}</strong><span>{t('sourcesDropHint')}</span></button>
        <form className="sources-url" onSubmit={event=>{event.preventDefault();void importUrl()}}><label htmlFor={id+'-url'}>{t('sourceUrl')}</label><p>{t('sourcesUrlHint')}</p>
          <div><input id={id+'-url'} type="url" required pattern="https?://.*" placeholder="https://example.com" value={url} disabled={disabled} onChange={event=>setUrl(event.target.value)}/>
            <button className="memories-button nova-settings-secondary" type="submit" disabled={disabled||!url.trim()||!view?.knowledge?.hostAcquisition}>{t('sourcesImportUrl')}</button></div></form>
      </div></div>}
    </div>
  </ModalHost>
}
