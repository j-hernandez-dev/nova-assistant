import {useCallback,useEffect,useId,useRef,useState,type CSSProperties} from 'react'
import type {StorageFile,StorageOverview} from '../../shared/storage'
import {useI18n} from '../i18n'
import {storageBytes,storageCategoryHint,storageCategoryKey,storageCategoryKeys,storageGroups,storageSelectedFiles,storageSelectionTarget} from '../storage_presentation'
import {SettingsSelect} from './SettingsSelect'
import {NovaIcon} from './NovaIcon'
import {DataActionDock} from './DataActionDock'
import '../storage.css'
import '../data_table.css'

type Result<T=unknown>={success:boolean;data?:T;canceled?:boolean;error?:{code:string}}
type Feedback='delete'|'link'|'folder'|'download'|null
type Group={path:string|null;name:string}
/** Storage requests are host operations. The renderer never receives a writable filesystem path. */
export function StorageSettings({active=true,locked=false,projectRevision=''}:{active?:boolean;locked?:boolean;projectRevision?:string}){
  const {t,locale}=useI18n(),id=useId()
  const [overview,setOverview]=useState<StorageOverview|null>(null),[group,setGroup]=useState<Group|null>(null)
  const [files,setFiles]=useState<StorageFile[]>([]),[selected,setSelected]=useState<string[]>([])
  const [loading,setLoading]=useState(false),[filesLoading,setFilesLoading]=useState(false),[busy,setBusy]=useState(false)
  const [fileQuery,setFileQuery]=useState(''),[fileFilter,setFileFilter]=useState('')
  const [downloaded,setDownloaded]=useState(0)
  const [error,setError]=useState<string|null>(null),[feedback,setFeedback]=useState<Feedback>(null),[restart,setRestart]=useState(false)
  const alive=useRef(true),enabled=useRef(active),generation=useRef(0),fileEpoch=useRef(0),operation=useRef(false),groupRef=useRef(group)
  enabled.current=active;groupRef.current=group
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;generation.current++;fileEpoch.current++}},[])
  const current=useCallback((epoch:number)=>alive.current&&enabled.current&&generation.current===epoch,[])
  const loadOverview=useCallback(async()=>{
    const epoch=++generation.current
    setLoading(true)
    try{
      const result=await window.api.storageOverview()
      if(!current(epoch))return
      if(result.success){
        setOverview(result.data);setRestart(result.data.restartRequired)
        if(groupRef.current?.path&&!result.data.projects.some(project=>project.path===groupRef.current?.path)){
          fileEpoch.current++;groupRef.current=null;setGroup(null);setSelected([]);setFilesLoading(false)
        }
      }
      else if(!result.canceled)setError(result.error?.code||'STORAGE_UNAVAILABLE')
    }catch{if(current(epoch))setError('STORAGE_UNAVAILABLE')}
    finally{if(current(epoch))setLoading(false)}
  },[current])
  const loadFiles=useCallback(async(projectPath:string|null)=>{
    const epoch=++fileEpoch.current
    setFilesLoading(true)
    try{
      const result=await window.api.storageFiles(projectPath)
      if(!alive.current||!enabled.current||fileEpoch.current!==epoch)return
      if(result.success){setFiles(result.data.files);setSelected(previous=>storageSelectedFiles(result.data.files,previous))}
      else if(!result.canceled)setError(result.error?.code||'STORAGE_UNAVAILABLE')
    }catch{if(alive.current&&enabled.current&&fileEpoch.current===epoch)setError('STORAGE_UNAVAILABLE')}
    finally{if(alive.current&&enabled.current&&fileEpoch.current===epoch)setFilesLoading(false)}
  },[])
  useEffect(()=>{
    if(!active){generation.current++;fileEpoch.current++;return}
    setError(null);void loadOverview()
    if(groupRef.current)void loadFiles(groupRef.current.path)
  },[active,projectRevision,loadOverview,loadFiles])

  async function refresh(){
    if(operation.current||loading||filesLoading)return
    setFeedback(null);setError(null)
    await Promise.all([loadOverview(),...(groupRef.current?[loadFiles(groupRef.current.path)]:[])])
  }
  async function mutate(request:()=>Promise<Result>,done:Feedback,refreshAfter=true){
    if(locked||operation.current||!active)return
    operation.current=true;setBusy(true);setError(null);setFeedback(null)
    try{
      const result=await request()
      if(!alive.current)return
      if(result.canceled)return
      if(!result.success){setError(result.error?.code||'STORAGE_FAILED');return}
      const data=result.data as {restartRequired?:boolean;downloaded?:number}|undefined
      if(done==='download')setDownloaded(data?.downloaded||0)
      if(data?.restartRequired)setRestart(true)
      setFeedback(data?.restartRequired?null:done)
      if(refreshAfter){
        setSelected([])
        await Promise.all([loadOverview(),...(groupRef.current?[loadFiles(groupRef.current.path)]:[])])
      }
    }catch{if(alive.current)setError('STORAGE_OUTCOME_UNKNOWN')}
    finally{operation.current=false;if(alive.current)setBusy(false)}
  }
  function openGroup(next:Group){
    if(busy)return
    setFileQuery('');setFileFilter('');fileEpoch.current++;setGroup(next);groupRef.current=next;setFiles([]);setSelected([]);setError(null);setFeedback(null)
    void loadFiles(next.path)
  }
  function back(){if(busy)return;setFileQuery('');setFileFilter('');fileEpoch.current++;setGroup(null);groupRef.current=null;setSelected([]);setError(null);setFeedback(null);setFilesLoading(false)}
  const searchText=(value:string)=>value.normalize('NFD').replace(/\p{M}/gu,'').toLocaleLowerCase(locale)
  const visibleFiles=files.filter(file=>searchText(file.name).includes(searchText(fileFilter)))
  const disabled=locked||busy,selectedIds=storageSelectedFiles(visibleFiles,selected),target=storageSelectionTarget(files,selectedIds)
  const groups=storageGroups(overview?.projects||[]),allSelected=visibleFiles.length>0&&selectedIds.length===visibleFiles.length
  const categoryRows=Object.keys(storageCategoryKeys).map(key=>({id:key,bytes:overview?.categories.find(category=>category.id===key)?.bytes||0}))
  const errorKey=error==='STORAGE_BUSY'||error==='PROJECT_BUSY'||error==='CONFLICT_ACTIVE_OPERATION'?'storageBusy':error==='STORAGE_UNAVAILABLE'?'storageUnavailable':error==='STORAGE_OUTCOME_UNKNOWN'?'storageUnconfirmed':'storageError'
  const number=new Intl.NumberFormat(locale)
  function modified(value:string){const date=new Date(value);return Number.isNaN(date.valueOf())?t('storageUnknownDate'):new Intl.DateTimeFormat(locale,{dateStyle:'medium',timeStyle:'short'}).format(date)}
  return <div className="nova-storage-settings" data-file-page={!!group} aria-busy={busy}>
    <div className="nova-settings-introduction nova-section-introduction"><div><h2 id={id+'-title'}>{t('settingsStorage')}</h2><p>{t('settingsStorageHint')}</p></div>
      {!group&&<button className="nova-settings-reset" type="button" disabled={disabled||loading||filesLoading} aria-label={t('storageRefresh')} onClick={()=>void refresh()}><NovaIcon name="refresh" size={15}/><span>{t('memoriesRefresh')}</span></button>}</div>
    {restart&&<div className="nova-storage-restart" role="status"><p>{t('storageRestartHint')}</p><button className="nova-settings-secondary" type="button" disabled={disabled} onClick={()=>void mutate(()=>window.api.storageRestart(),null,false)}>{t('storageRestart')}</button></div>}
    <div className="nova-storage-feedback" aria-live="polite">
      {error?<div className="nova-settings-error" role="alert"><p>{t(errorKey)}</p><details><summary>{t('diagnosticDetails')}</summary><code>{error}</code></details></div>:
      feedback?<p role="status">{t(feedback==='delete'?'storageDeleteDone':feedback==='link'?'storageLinkDone':feedback==='download'?'storageDownloadDone':'storageFolderDone')}{feedback==='download'?`: ${number.format(downloaded)}`:''}</p>:null}
    </div>
    {!group?<div className="nova-storage-page" key="overview">
      <section className="nova-storage-summary" aria-labelledby={id+'-device'} aria-busy={loading}>
        <div className="nova-storage-summary-heading"><div><h3 id={id+'-device'}>{t('storageDevice')}</h3><p className="nova-storage-total"><strong>{overview?storageBytes(overview.totalBytes,locale):'—'}</strong> {t('storageTotal')}</p></div>
          <span className="nova-storage-measuring" role="status">{loading?t(overview?'storageUpdating':'storageLoading'):null}</span></div>
        <div className="nova-storage-bar" role="img" aria-label={categoryRows.map(category=>`${t(storageCategoryKey(category.id))}: ${storageBytes(category.bytes,locale)}`).join(', ')}>
          {categoryRows.map(category=><span key={category.id} data-storage-category={category.id} title={`${t(storageCategoryKey(category.id))}: ${storageBytes(category.bytes,locale)}`}
            style={{'--storage-share':`${overview?.totalBytes?category.bytes/overview.totalBytes*100:0}%`} as CSSProperties}/>)}</div>
        <ul className="nova-storage-legend">{categoryRows.map(category=><li key={category.id} data-storage-category={category.id}><span><i/>{t(storageCategoryKey(category.id))}</span><strong>{overview?storageBytes(category.bytes,locale):'—'}</strong></li>)}</ul>
        <p className="nova-storage-note">{t('storageDataOnly')}</p>
        {!!overview?.warnings?.length&&<p className="nova-storage-note" role="status">{t('storagePartial')}</p>}
      </section>
      <section className="nova-preferences-group" aria-labelledby={id+'-folders'}><h3 id={id+'-folders'}>{t('storageFolders')}</h3>
        <div className="nova-settings-card nova-preferences-list">{(overview?.folders||[]).map(folder=><div className="nova-preference-row nova-storage-folder" key={folder.id}>
          <div><h4>{t(storageCategoryKey(folder.category))}</h4><p>{t(storageCategoryHint(folder.category))}</p>
            <p className="nova-storage-path" title={(folder.paths||[folder.path]).join('\n')}>{folder.path}</p>
            <span className="nova-storage-folder-size">{storageBytes(folder.bytes,locale)}{!folder.exists?` · ${t('storageFolderAbsent')}`:''}</span></div>
          <div className="nova-storage-folder-actions"><button className="nova-settings-secondary" type="button" disabled={disabled||!folder.exists} onClick={()=>void mutate(()=>window.api.storageOpenFolder(folder.id),null,false)}>{t('storageView')}</button>
            <button className="nova-settings-danger" type="button" disabled={disabled||!folder.exists} onClick={()=>void mutate(()=>window.api.storageDeleteFolder(folder.id),'folder')}>{t('storageDelete')}</button></div>
        </div>)}{!overview&&<div className="nova-storage-folder-placeholder" role="status">{t(loading?'storageLoading':'storageUnavailable')}</div>}</div>
      </section>
      <section className="nova-preferences-group" aria-labelledby={id+'-manage'}><h3 id={id+'-manage'}>{t('storageManage')}</h3>
        <div className="nova-settings-card nova-preferences-list">{groups.map(project=><div className="nova-preference-row nova-storage-project" key={project.path??'unlinked'} data-storage-project={project.path??''}>
          <span><strong>{project.path===null?t('storageUnlinked'):project.name}</strong>
            <small>{storageBytes(project.bytes,locale)} · {number.format(project.fileCount)} {t(project.fileCount===1?'storageFileSingular':'storageFileCount')}</small></span>
          <button className="nova-storage-project-open" type="button" disabled={disabled||!overview} aria-label={`${t('storageView')}: ${project.path===null?t('storageUnlinked'):project.name}`}
            onClick={()=>openGroup(project)}><NovaIcon name="chevron" size={18}/></button></div>)}</div>
      </section>
    </div>:<section className="nova-storage-page nova-storage-file-page nova-data-region" key={group.path??'unlinked'} aria-labelledby={id+'-files'}>
      <div className="nova-data-scroll nova-storage-file-scroll">
      <button className="nova-storage-back" type="button" disabled={busy} onClick={back}><NovaIcon name="back" size={17}/>{t('storageBack')}</button>
      <form className="nova-data-search nova-storage-search" role="search" onSubmit={event=>{event.preventDefault();if(disabled)return;setFileFilter(fileQuery.trim());setSelected([])}}>
        <NovaIcon name="search" size={18}/><input type="search" aria-label={t('storageSearchFiles')} placeholder={t('storageSearchPlaceholder')} value={fileQuery} maxLength={4096} disabled={disabled||filesLoading}
          onChange={event=>setFileQuery(event.target.value)}/>
        <button type="submit" className="nova-search-submit" disabled={disabled||filesLoading} aria-label={t('storageSearchFiles')}><NovaIcon name="forward" size={18}/></button>
        <button type="button" className="nova-search-refresh" disabled={disabled||loading||filesLoading} aria-label={t('storageRefresh')} title={t('storageRefresh')} onClick={()=>void refresh()}><NovaIcon name="sync" size={17} strokeWidth={1.6}/></button>
      </form>
      <div className="nova-storage-file-heading"><div><h3 id={id+'-files'}>{group.path===null?t('storageUnlinked'):group.name}</h3><p>{storageBytes(files.reduce((total,file)=>total+file.bytes,0),locale)} · {number.format(files.length)} {t(files.length===1?'storageFileSingular':'storageFileCount')}</p></div>
        <span className="nova-storage-measuring" role="status">{filesLoading?t(files.length?'storageUpdating':'storageFilesLoading'):null}</span></div>
      <div className="nova-storage-table-wrap nova-data-table-wrap" aria-busy={filesLoading}><table className="nova-storage-table nova-data-table"><thead><tr><th className="nova-storage-check"><input type="checkbox" aria-label={t('storageSelectAll')} checked={allSelected} disabled={disabled||filesLoading||!visibleFiles.length}
        ref={element=>{if(element)element.indeterminate=selectedIds.length>0&&!allSelected}} onChange={event=>setSelected(event.target.checked?visibleFiles.map(file=>file.id):[])}/></th>
        <th scope="col">{t('storageName')}</th><th scope="col">{t('storageModified')}</th><th scope="col">{t('storageSize')}</th></tr></thead>
        <tbody>{visibleFiles.map(file=><tr key={file.id} data-selected={selectedIds.includes(file.id)||undefined}>
          <td className="nova-storage-check"><input id={id+'-file-'+file.id} type="checkbox" aria-label={`${t('storageSelectFile')}: ${file.name}`} checked={selectedIds.includes(file.id)} disabled={disabled||filesLoading}
            onChange={event=>setSelected(previous=>event.target.checked?[...new Set([...previous,file.id])]:previous.filter(value=>value!==file.id))}/></td>
          <td><span className="nova-storage-filename" title={file.name}><NovaIcon name="file-read" size={18}/><span>{file.name}</span></span></td>
          <td><time dateTime={file.modifiedAt}>{modified(file.modifiedAt)}</time></td><td>{storageBytes(file.bytes,locale)}</td></tr>)}</tbody></table>
        {!visibleFiles.length&&<div className="nova-storage-empty" role="status"><NovaIcon name="database" size={30}/><strong>{filesLoading?t('storageLoading'):t(files.length?'storageNoMatches':'storageNoFiles')}</strong><p>{t(files.length?'storageNoMatchesHint':group.path===null?'storageNoUnlinkedHint':'storageNoFilesHint')}</p></div>}</div>
      </div>
      <DataActionDock className="nova-storage-selection" visible={selectedIds.length>0}>
        <span className="nova-data-selection-count">{number.format(selectedIds.length)} {t(selectedIds.length===1?'storageSelectedSingular':'storageSelected')}</span><div><SettingsSelect value={target} disabled={disabled||filesLoading||!selectedIds.length} aria-label={t('storageLink')} data-settings-select="storageProject"
          options={[...(target==='__mixed__'?[{value:'__mixed__',label:t('storageMixed'),disabled:true}]:[]),{value:'',label:t('storageUnlink')},...groups.filter(project=>project.path!==null).map(project=>({value:project.path!,label:project.name,...(groups.filter(other=>other.path!==null&&other.name===project.name).length>1?{description:project.path!}:{})}))]}
          onChange={value=>void mutate(()=>window.api.storageMove(selectedIds,value||null),'link')}/>
          <button className="nova-settings-secondary" type="button" disabled={disabled||filesLoading||!selectedIds.length} onClick={()=>void mutate(()=>window.api.storageDownload(selectedIds),'download',false)}>{t('storageDownload')}</button>
          <button className="nova-settings-danger" type="button" disabled={disabled||filesLoading||!selectedIds.length} onClick={()=>void mutate(()=>window.api.storageDeleteFiles(selectedIds),'delete')}>{t('storageDelete')}</button></div>
      </DataActionDock>
    </section>}
  </div>
}
