import { useEffect, useLayoutEffect, useId, useRef, useState } from 'react'
import type { DesktopSessionView } from '../../shared/application'
import { useI18n } from '../i18n'
import { SettingsActionFeedback, useSettingsAction } from '../settings_actions'
import { SettingsSelect } from './SettingsSelect'
import { NovaIcon } from './NovaIcon'
import {DataActionDock} from './DataActionDock'
import type {ProposalNotifications} from './MemoryWindow'
import '../data_table.css'

type Props = { view: DesktopSessionView | null; active?: boolean; locked?: boolean;proposalNotifications?:ProposalNotifications }
export type MemoryInspection = { memoryId: string; revision: number; canonicalText: string; kind: string;
  scopeKind: string; status: string; sensitivityClass?: string; hidden: boolean }
type Proposal = { jobId: string; revision: number; proposalId: string; text: string; kind: string; scopeKind: string }
const kinds = ['PREFERENCE', 'SEMANTIC_FACT', 'WORKSPACE_FACT', 'EPISODE', 'PROCEDURE'] as const
const kindKeys = ['memorySettingsPreference', 'memorySettingsFact', 'memorySettingsProjectFact', 'memorySettingsEpisode', 'memorySettingsProcedure'] as const
const statusKeys = { ACTIVE: 'memorySettingsActive', SUPERSEDED: 'memorySettingsSuperseded', CONFLICTED: 'memorySettingsConflicted',
  RETRACTED: 'memorySettingsRetracted', EXPIRED: 'memorySettingsExpired', DELETED: 'memorySettingsDeleted' } as const
const object = (value: any) => value && typeof value === 'object' && !Array.isArray(value)
const identity = (value: unknown): value is string => typeof value === 'string' && value.length > 0 && value.length <= 128

/** Inspection data never becomes a chat message, a tool argument or authority. */
export function memoryInspection(value: any): MemoryInspection | null {
  if (!object(value) || !identity(value.memoryId) || !Number.isSafeInteger(value.revision) || value.revision < 1
    || typeof value.canonicalText !== 'string' || !kinds.includes(value.kind) || !['WORKSPACE', 'GLOBAL_PROFILE'].includes(value.scopeKind)
    || !Object.prototype.hasOwnProperty.call(statusKeys, value.status)) return null
  return { memoryId: value.memoryId, revision: value.revision, canonicalText: value.canonicalText,
    kind: value.kind, scopeKind: value.scopeKind, status: value.status, sensitivityClass: value.sensitivityClass,
    hidden: value.sensitivityClass === 'SENSITIVE' && value.canonicalText === '[SENSITIVE — explicit inspection required]' }
}
export function memoryProposals(value: unknown): Proposal[] {
  return Array.isArray(value) ? value.flatMap(row => object(row) && identity(row.jobId) && Number.isSafeInteger(row.revision)
    && row.revision >= 1 && object(row.proposal) && identity(row.proposal.proposalId)
    && typeof row.proposal.text === 'string' && kinds.includes(row.proposal.kind)
    && ['WORKSPACE', 'GLOBAL_PROFILE'].includes(row.proposal.scopeKind)
    ? [{ jobId: row.jobId, revision: row.revision, proposalId: row.proposal.proposalId,
      text: row.proposal.text, kind: row.proposal.kind, scopeKind: row.proposal.scopeKind }] : []) : []
}
export function memoryRecordMutation(record: MemoryInspection, text?: string, consentSensitive = false): Record<string, unknown> {
  return { memoryId: record.memoryId, revision: record.revision,
    ...(text !== undefined ? { text, ...(consentSensitive ? { consentSensitive: true } : {}) } : {}) }
}
export function memoryProposalMutation(proposal: Proposal, resolution?: 'create' | 'supersede' | 'conflict'): Record<string, unknown> {
  return { jobId: proposal.jobId, proposalId: proposal.proposalId, revision: proposal.revision,
    ...(resolution ? { resolution } : {}) }
}


type Tab = 'saved' | 'add' | 'proposals'
type InspectionState = { scope:string; records:MemoryInspection[]|null; nextCursor:string|null;
  proposals:Proposal[]|null }
const empty=(scope:string):InspectionState=>({scope,records:null,nextCursor:null,proposals:null})

export function MemoryRecords({view,active=true,locked=false,proposalNotifications}:Props){
  const {t}=useI18n(),id=useId()
  const scope=(view?.sessionId||'')+':'+(view?.workspace||'')+':'+!!view?.status.connected
  const action=useSettingsAction(scope),liveScope=useRef(scope),alive=useRef(true),activeRef=useRef(active)
  liveScope.current=scope;activeRef.current=active
  const [tab,setTab]=useState<Tab>('saved')
  const proposalsVisible=proposalNotifications?.setTabVisible
  useEffect(()=>{proposalsVisible?.(active&&tab==='proposals');return()=>proposalsVisible?.(false)},[active,tab,proposalsVisible])
  const [loaded,setLoaded]=useState<InspectionState>(()=>empty(scope))
  const data=loaded.scope===scope?loaded:empty(scope)
  const [filterScope,setFilterScope]=useState('ALL'),[includeSensitive,setIncludeSensitive]=useState(false)
  const [query,setQuery]=useState(''),[loading,setLoading]=useState(active&&!!view?.status.ready)
  const listEpoch=useRef(0),[requestKind,setRequestKind]=useState<'read'|'write'>('read')
  const [text,setText]=useState(''),[kind,setKind]=useState('WORKSPACE_FACT')
  const [writeScope,setWriteScope]=useState('WORKSPACE'),[sensitive,setSensitive]=useState(false)
  const [selected,setSelected]=useState<string[]>([])
  const [editing,setEditing]=useState(false),[drafts,setDrafts]=useState<Record<string,MemoryDraft>>({})
  const [resolution,setResolution]=useState<'create'|'supersede'|'conflict'>('create')
  const [uncertainEffect,setUncertainEffect]=useState(false),[notice,setNotice]=useState<string|null>(null)
  const ready=active&&!!view?.status.ready&&view.status.connected&&!view.recovering&&!view.gap&&!!view.memory
  const canRead=ready&&!locked&&!view?.activeTurnId&&!view?.activeGenerationId&&!view?.approvals?.length
    &&!view?.inputs?.length&&!view?.memory?.maintenanceBusy
  const disabled=!canRead||action.busy
  const mutationDisabled=disabled||uncertainEffect
  useEffect(()=>{alive.current=true;return()=>{alive.current=false}},[])
  useEffect(()=>{
    setLoaded(empty(scope));setTab('saved');setQuery('');setText('');setIncludeSensitive(false)
    setFilterScope('ALL');setWriteScope('WORKSPACE');setKind('WORKSPACE_FACT');setSensitive(false)
    setSelected([]);setEditing(false);setDrafts({});setUncertainEffect(false)
    setLoading(activeRef.current&&!!view?.status.ready&&!!view.status.connected&&!!view.memory);setNotice(null)
  },[scope])
  const current=()=>alive.current&&activeRef.current&&liveScope.current===scope
  async function invoke(name:string,args:Record<string,unknown>,mutation=false){
    if(disabled||(mutation&&mutationDisabled))return null
    setRequestKind(mutation?'write':'read')
    const receipt=await action.run(async()=>{
      let result=await window.api.memoryCommand(name,args)
      // Only ordinary inspection reads may wait for an unrelated revision or
      // busy worker. Sensitive inspection and every write retain one request.
      const ordinaryRead=!mutation&&['memory_list','memory_search','memory_proposals'].includes(name)&&args.includeSensitive!==true
      for(let attempt=0;ordinaryRead&&attempt<3&&current()&&['REVISION_CONFLICT','CONFLICT_ACTIVE_OPERATION','PROJECT_BUSY','MEMORY_BUSY','MEMORY_MAINTENANCE_BUSY'].includes(result.error?.code||'');attempt++){
        await new Promise(resolve=>setTimeout(resolve,80*2**attempt))
        if(!current())return result
        result=await window.api.memoryCommand(name,args)
      }
      if(current()&&mutation&&(result.error?.outcomeUnknown||result.error?.code==='OUTCOME_UNKNOWN'))setUncertainEffect(true)
      return result
    })
    return current()&&receipt?.completed?receipt.data||{}:null
  }
  async function inspectPage(search=false,cursor?:string,scopeValue=filterScope,reveal=includeSensitive){
    if(disabled)return false
    const request=++listEpoch.current
    setLoading(true)
    const result=await invoke(search?'memory_search':'memory_list',{scope:scopeValue,limit:20,includeSensitive:reveal,
      ...(search?{query:query.trim()}:cursor?{cursor}:{})})
    if(!current()||request!==listEpoch.current)return false
    setLoading(false)
    if(result){
    if(!cursor)setSelected([])
    setLoaded(old=>{
      const rows=Array.isArray(result.records)?result.records.map(memoryInspection).filter((r:MemoryInspection|null):r is MemoryInspection=>!!r):[]
      const records=cursor?[...(old.records||[]),...rows.filter((r:MemoryInspection)=>!old.records?.some(v=>v.memoryId===r.memoryId))]:rows
      return {...old,scope,records,nextCursor:!search&&typeof result.nextCursor==='string'?result.nextCursor:null}
    })
    }
    return !!result
  }
  async function inspectProposals(){
    const result=await invoke('memory_proposals',{})
    if(result){setLoaded(old=>({...old,scope,proposals:memoryProposals(result.proposals)}));proposalNotifications?.observe(result.proposals)}
  }
  // Opening the window or a tab loads normal records once. Host snapshots do not poll or reset the list.
  useEffect(()=>{
    if(!canRead||action.busy||(requestKind==='read'&&(action.errorCode||action.unconfirmed)))return
    // React StrictMode replays mount effects in development. Defer the read
    // until that setup/cleanup pass finishes so it cannot start two workers.
    const timer=setTimeout(()=>{
      if(!current())return
      if(tab==='saved'&&data.records===null)void inspectPage(false,undefined,'ALL',false)
      else if(data.proposals===null)void inspectProposals()
    },0)
    return()=>clearTimeout(timer)
  },[active,scope,tab,canRead,action.busy,action.errorCode,action.unconfirmed,requestKind])
  async function refreshAfterWrite(message:string){
    setNotice(message);setLoaded(empty(scope));setQuery('');setFilterScope('ALL');setIncludeSensitive(false)
    setSelected([]);setEditing(false);setDrafts({})
    setTab('saved');await inspectPage(false,undefined,'ALL',false)
  }
  async function remember(){
    const result=await invoke('memory_remember',{kind,text,scope:writeScope,
      ...(sensitive?{sensitive:true,consentSensitive:true}:{})},true)
    if(result){setText('');setSensitive(false);await refreshAfterWrite('memoriesAdded')}
  }
  function startEditing(){
    setSelected([])
    setDrafts(Object.fromEntries((data.records||[]).filter(editable).map(record=>[record.memoryId,draftOf(record)])))
    setEditing(true);setNotice(null)
  }
  function changeDraft(record:MemoryInspection,patch:Partial<MemoryDraft>){
    setDrafts(previous=>({...previous,[record.memoryId]:{...previous[record.memoryId],...patch}}))
  }
  async function changeSensitivity(record:MemoryInspection,next:boolean){
    if(mutationDisabled)return
    setRequestKind('read')
    const receipt=await action.run(()=>window.api.memoryEditSensitivity({memoryId:record.memoryId,revision:record.revision,sensitive:next}))
    if(current()&&receipt?.completed&&typeof receipt.data?.token==='string')changeDraft(record,{sensitive:next,consentToken:receipt.data.token})
  }
  const changedRecords=(data.records||[]).filter(record=>drafts[record.memoryId]&&draftChanged(record,drafts[record.memoryId]))
  async function saveEdits(){
    if(!editing||!changedRecords.length)return
    const records=changedRecords.map(record=>({memoryId:record.memoryId,revision:record.revision,...drafts[record.memoryId]}))
    const result=await invoke('memory_edit',{records},true)
    if(result)await refreshAfterWrite('memoriesUpdated')
  }
  const selectedRecords=(data.records||[]).filter(record=>selected.includes(record.memoryId))
  const allSelected=!!data.records?.length&&selectedRecords.length===data.records.length
  async function deleteSelected(){
    if(editing||!selectedRecords.length)return
    const result=await invoke('memory_delete',{records:selectedRecords.map(record=>({memoryId:record.memoryId,revision:record.revision}))},true)
    if(result)await refreshAfterWrite('memoriesForgotten')
  }
  async function decideProposal(proposal:Proposal,confirm:boolean){
    const result=await invoke(confirm?'memory_confirm':'memory_reject',memoryProposalMutation(proposal,confirm?resolution:undefined),true)
    if(result){
      setNotice(confirm?'memoriesProposalSaved':'memoriesProposalRejected')
      setLoaded(old=>({...old,scope,proposals:null,records:null,nextCursor:null}))
      await inspectProposals()
    }
  }
  const tabs=[['saved','memoriesSaved'],['add','memoriesAdd'],['proposals','memorySettingsProposals']] as const
  const scopes=[{value:'ALL',label:t('memoriesProjectAndProfile')},{value:'WORKSPACE',label:t('memorySettingsWorkspace')},{value:'GLOBAL_PROFILE',label:t('memorySettingsGlobal')}]
  const emptyState=(title:Parameters<typeof t>[0],hint:Parameters<typeof t>[0])=><div className="memories-empty"><NovaIcon name="memories" size={34}/><h3>{t(title)}</h3><p>{t(hint)}</p></div>
  return <div className="nova-memory-records">
    <nav className="memories-tabs" role="tablist" aria-label={t('memoriesSections')}>
      {tabs.map(([value,label],index)=><button type="button" role="tab" id={id+'-tab-'+value} key={value} data-memory-tab={value}
        aria-selected={tab===value} aria-controls={id+'-panel-'+value} tabIndex={tab===value?0:-1}
        disabled={action.busy||editing} onClick={()=>setTab(value)} onKeyDown={event=>{
          if(editing||action.busy)return
          let next=index
          if(event.key==='ArrowRight')next=(index+1)%tabs.length
          else if(event.key==='ArrowLeft')next=(index+tabs.length-1)%tabs.length
          else if(event.key==='Home')next=0
          else if(event.key==='End')next=tabs.length-1
          else return
          event.preventDefault();setTab(tabs[next][0]);document.getElementById(id+'-tab-'+tabs[next][0])?.focus()
        }}>{t(label)}{value==='proposals'&&!!proposalNotifications?.counts.tab&&<span className="memories-count" data-memory-notification="tab" aria-label={`${proposalNotifications.counts.tab} ${t('memoriesUnreadProposals')}`}>{proposalNotifications.counts.tab>99?'99+':proposalNotifications.counts.tab}</span>}</button>)}
    </nav>
    <div className="memories-content" data-table-view={tab==='saved'}>
      {active&&tab!=='saved'&&!ready&&<p className="memories-notice" role="status">{t('memorySettingsUnavailable')}</p>}
      {active&&tab!=='saved'&&ready&&!action.busy&&(locked||!!view?.activeTurnId||!!view?.activeGenerationId||!!view?.memory?.maintenanceBusy)&&<p className="memories-notice" role="status">{t('memoriesBusy')}</p>}
      <SettingsActionFeedback action={{...action,busy:requestKind==='write'&&action.busy,result:null}}/>
      {uncertainEffect&&<p className="memories-notice" role="alert">{t('memorySettingsUnconfirmed')}</p>}
      {notice&&!action.errorCode&&<p className="memories-feedback" role="status">{t(notice as Parameters<typeof t>[0])}</p>}
      <section className="memories-saved-panel nova-data-region" hidden={tab!=='saved'} role="tabpanel" id={id+'-panel-saved'} aria-labelledby={id+'-tab-saved'}>
        <div className="nova-data-scroll memories-saved-scroll">
        <div className="memories-toolbar">
          <form className="memories-search nova-data-search" onSubmit={event=>{event.preventDefault();if(!editing)void inspectPage(!!query.trim())}}>
            <NovaIcon name="search" size={18}/><input id={id+'-query'} aria-label={t('memorySettingsQuery')} placeholder={t('memoriesSearchPlaceholder')}
              value={query} maxLength={4096} disabled={disabled||editing} onChange={event=>setQuery(event.target.value)}/>
            <button type="submit" className="memories-icon nova-search-submit" aria-label={t('memorySettingsSearch')} disabled={disabled||editing}><NovaIcon name="forward" size={18}/></button>
            <button className="memories-refresh nova-search-refresh" type="button" disabled={disabled||editing} onClick={()=>void inspectPage(!!query.trim())}
              aria-label={t('memoriesRefresh')} title={t('memoriesRefresh')}><NovaIcon name="sync" size={17} strokeWidth={1.6}/></button>
          </form>
          <SettingsSelect id={id+'-scope'} aria-label={t('memorySettingsScope')} value={filterScope} disabled={disabled||editing} options={scopes}
            onChange={value=>{setFilterScope(value);setLoaded(empty(scope));void inspectPage(false,undefined,value)}}/>
        </div>
        <div className="memories-list-options"><label><input id={id+'-reveal'} type="checkbox" checked={includeSensitive} disabled={disabled||editing}
          onChange={event=>{
            const reveal=event.target.checked
            if(!reveal){setIncludeSensitive(false);setLoaded(empty(scope));void inspectPage(false,undefined,filterScope,false)}
            else void inspectPage(false,undefined,filterScope,true).then(confirmed=>{if(current()&&confirmed)setIncludeSensitive(true)})
          }}/>{t('memoriesShowSensitive')}</label>
          <span className="memories-load-status" role="status" title={!ready?t('memorySettingsUnavailable'):!canRead&&!action.busy?t('memoriesBusy'):undefined}>{!ready?t('memorySettingsUnavailable'):!canRead&&!action.busy?t('memoriesBusy'):loading?t('memoriesLoading'):data.records?t('memoriesShown')+': '+data.records.length:''}</span></div>
        {data.records===null?emptyState(loading?'memoriesLoading':'memoriesNotLoaded','memoriesListHint'):
          data.records.length===0?emptyState('memoriesEmpty','memoriesEmptyHint'):
          <>
            <div className="nova-data-table-wrap" aria-busy={loading}><table className="nova-data-table memories-table">
              <thead><tr><th className="memories-select-column"><input type="checkbox" aria-label={t('memoriesSelectAll')} checked={allSelected} disabled={disabled||editing||!data.records.length}
                ref={element=>{if(element)element.indeterminate=selectedRecords.length>0&&!allSelected}}
                onChange={event=>setSelected(event.target.checked?data.records!.map(record=>record.memoryId):[])}/></th><th scope="col">{t('memoriesColumnMemory')}</th><th scope="col">{t('memorySettingsKind')}</th><th scope="col">{t('memorySettingsScope')}</th><th scope="col">{t('memoriesSensitiveContent')}</th></tr></thead>
              <tbody>{data.records.map(record=>{
                const draft=drafts[record.memoryId],edit=editing&&editable(record)&&!!draft
                return <tr key={record.memoryId} data-memory-record={record.memoryId} data-editing={edit||undefined} data-selected={selected.includes(record.memoryId)||undefined}>
                  <td className="memories-select-column"><input type="checkbox" aria-label={t('memoriesSelectRecord')} checked={selected.includes(record.memoryId)} disabled={disabled||editing}
                    onChange={event=>setSelected(previous=>event.target.checked?[...new Set([...previous,record.memoryId])]:previous.filter(value=>value!==record.memoryId))}/></td>
                  <td>{edit?<GrowingMemoryText value={draft.text} label={t('memoriesColumnMemory')} disabled={mutationDisabled} onChange={text=>changeDraft(record,{text})}/>:
                    <div className="memories-table-text">{record.hidden?t('memorySettingsHidden'):record.canonicalText}</div>}
                    {!['ACTIVE','CONFLICTED'].includes(record.status)&&<small className="memories-meta">{t(statusKeys[record.status as keyof typeof statusKeys])}</small>}</td>
                  <td>{edit?<SettingsSelect value={draft.kind} aria-label={t('memorySettingsKind')} disabled={mutationDisabled}
                    options={kinds.filter(value=>draft.scope!=='GLOBAL_PROFILE'||value!=='WORKSPACE_FACT').map(value=>({value,label:t(kindKeys[kinds.indexOf(value)])}))}
                    onChange={kind=>changeDraft(record,{kind})}/>:t(kindKeys[kinds.indexOf(record.kind as typeof kinds[number])])}</td>
                  <td>{edit?<SettingsSelect value={draft.scope} aria-label={t('memorySettingsScope')} disabled={mutationDisabled} options={scopes.slice(1)}
                    onChange={scope=>changeDraft(record,{scope,...(scope==='GLOBAL_PROFILE'&&draft.kind==='WORKSPACE_FACT'?{kind:'PREFERENCE'}:{})})}/>:t(record.scopeKind==='WORKSPACE'?'memorySettingsWorkspace':'memorySettingsGlobal')}</td>
                  <td><input type="checkbox" aria-label={t('memoriesSensitiveContent')} checked={edit?draft.sensitive:record.sensitivityClass==='SENSITIVE'} disabled={!edit||mutationDisabled}
                    onChange={event=>void changeSensitivity(record,event.target.checked)}/></td>
                </tr>
              })}</tbody></table></div>
            {data.nextCursor&&<button className="memories-button memories-more" disabled={disabled||editing} onClick={()=>void inspectPage(false,data.nextCursor!)}>{t('memoriesLoadMore')}</button>}
          </>}
        </div>
        <DataActionDock className="memories-table-actions" visible={!!data.records?.length}>
          {!!selectedRecords.length&&<span className="nova-data-selection-count">{selectedRecords.length} {t(selectedRecords.length===1?'memoriesSelectedSingular':'memoriesSelected')}</span>}
          {editing?<><button className="memories-button" type="button" disabled={action.busy} onClick={()=>{setEditing(false);setDrafts({});setNotice(null)}}>{t('memoriesDiscard')}</button>
            <button className="memories-button primary" type="button" disabled={mutationDisabled||!changedRecords.length||changedRecords.some(record=>!drafts[record.memoryId].text.trim())} onClick={()=>void saveEdits()}>{t('memoriesSave')}</button></>:
            selectedRecords.length?<button className="nova-settings-danger" type="button" disabled={mutationDisabled} onClick={()=>void deleteSelected()}>{t('memoriesDelete')}</button>:
            <button className="memories-button" type="button" disabled={mutationDisabled||!data.records?.some(editable)} onClick={startEditing}>{t('memoriesEdit')}</button>}
        </DataActionDock>
      </section>
      <section hidden={tab!=='add'} role="tabpanel" id={id+'-panel-add'} aria-labelledby={id+'-tab-add'}>
        <form className="memories-editor" onSubmit={event=>{event.preventDefault();void remember()}}>
          <h2>{t('memoriesAdd')}</h2><p className="memories-hint">{t('memoriesAddHint')}</p>
          <label htmlFor={id+'-text'}>{t('memorySettingsText')}</label><textarea id={id+'-text'} rows={6} maxLength={4096} value={text}
            disabled={mutationDisabled} placeholder={t('memoriesTextPlaceholder')} onChange={event=>setText(event.target.value)}/>
          <div className="memories-fields"><div><label htmlFor={id+'-kind'}>{t('memorySettingsKind')}</label>
            <SettingsSelect id={id+'-kind'} aria-label={t('memorySettingsKind')} value={kind} disabled={mutationDisabled} onChange={setKind}
              options={kinds.filter(value=>writeScope!=='GLOBAL_PROFILE'||value!=='WORKSPACE_FACT').map(value=>({value,label:t(kindKeys[kinds.indexOf(value)])}))}/></div>
            <div><label htmlFor={id+'-write-scope'}>{t('memorySettingsScope')}</label>
              <SettingsSelect id={id+'-write-scope'} aria-label={t('memorySettingsScope')} value={writeScope} disabled={mutationDisabled} onChange={value=>{
                setWriteScope(value);if(value==='GLOBAL_PROFILE'&&kind==='WORKSPACE_FACT')setKind('PREFERENCE')
              }}
                options={scopes.slice(1)}/></div></div>
          <label className="memories-checkbox"><input id={id+'-sensitive'} type="checkbox" checked={sensitive} disabled={mutationDisabled}
            onChange={event=>setSensitive(event.target.checked)}/>{t('memoriesSensitiveContent')}</label>
          <p className="memories-hint">{t('memoriesSensitiveHint')}</p>
          <div className="memories-actions"><button className="memories-button primary" type="submit" disabled={mutationDisabled||!text.trim()}>{t('memorySettingsRemember')}</button></div>
        </form>
      </section>
      <section hidden={tab!=='proposals'} role="tabpanel" id={id+'-panel-proposals'} aria-labelledby={id+'-tab-proposals'}>
        <div className="memories-proposal-heading"><div><h2>{t('memorySettingsProposals')}</h2><p className="memories-hint">{t('memoriesProposalsHint')}</p></div>
          <button className="memories-button" disabled={disabled} onClick={()=>void inspectProposals()}><NovaIcon name="refresh" size={17}/>{t('memoriesRefresh')}</button></div>
        {data.proposals===null?emptyState('memoriesLoading','memoriesProposalsHint'):data.proposals.length===0?emptyState('memoriesNoProposals','memoriesNoProposalsHint'):
          <><div className="memories-proposal-resolution"><label htmlFor={id+'-resolution'}>{t('memorySettingsResolution')}</label>
            <SettingsSelect id={id+'-resolution'} value={resolution} aria-label={t('memorySettingsResolution')} disabled={mutationDisabled} onChange={value=>setResolution(value as typeof resolution)}
              options={[{value:'create',label:t('memorySettingsCreate')},{value:'supersede',label:t('memorySettingsSupersede')},{value:'conflict',label:t('memorySettingsConflict')}]}/></div>
            <div className="memories-proposals">{data.proposals.map(proposal=><article className="memories-proposal" key={proposal.jobId+':'+proposal.proposalId} data-memory-proposal>
              <p>{proposal.text}</p><small>{t(kindKeys[kinds.indexOf(proposal.kind as typeof kinds[number])])} · {t(proposal.scopeKind==='WORKSPACE'?'memorySettingsWorkspace':'memorySettingsGlobal')}</small>
              <div className="memories-actions"><button className="memories-button primary" disabled={mutationDisabled} onClick={()=>void decideProposal(proposal,true)}>{t('memoriesApprove')}</button>
                <button className="memories-button" disabled={mutationDisabled} onClick={()=>void decideProposal(proposal,false)}>{t('memoriesReject')}</button></div>
            </article>)}</div></>}
      </section>
    </div>
  </div>
}
type MemoryDraft={text:string;kind:string;scope:string;sensitive:boolean;consentToken?:string}
const editable=(record:MemoryInspection)=>!record.hidden&&['ACTIVE','CONFLICTED'].includes(record.status)
const draftOf=(record:MemoryInspection):MemoryDraft=>({text:record.canonicalText,kind:record.kind,scope:record.scopeKind,sensitive:record.sensitivityClass==='SENSITIVE'})
const draftChanged=(record:MemoryInspection,draft:MemoryDraft)=>draft.text!==record.canonicalText||draft.kind!==record.kind||draft.scope!==record.scopeKind||draft.sensitive!==(record.sensitivityClass==='SENSITIVE')
function GrowingMemoryText({value,label,disabled,onChange}:{value:string;label:string;disabled:boolean;onChange:(value:string)=>void}){
  const input=useRef<HTMLTextAreaElement>(null)
  useLayoutEffect(()=>{
    const element=input.current;if(!element)return
    const resize=()=>{element.style.height='0px';element.style.height=(element.scrollHeight+element.offsetHeight-element.clientHeight)+'px'}
    resize();let width=element.clientWidth;const observer=new ResizeObserver(()=>{if(element.clientWidth!==width){width=element.clientWidth;resize()}});observer.observe(element);return()=>observer.disconnect()
  },[value])
  return <textarea ref={input} className="memories-table-input" rows={1} maxLength={4096} aria-label={label} value={value} disabled={disabled} onChange={event=>onChange(event.target.value)}/>
}
