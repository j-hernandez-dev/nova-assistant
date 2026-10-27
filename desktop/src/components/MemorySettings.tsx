import {useEffect,useId,useRef,useState} from 'react'
import type {DesktopSessionView,MemoryControlResult,MemoryStatus} from '../../shared/application'
import type {ProjectState} from '../types'
import {useI18n} from '../i18n'
import {sameProjectPath} from '../project_presentation'
import {useSettingsAction} from '../settings_actions'
import {SettingsSelect} from './SettingsSelect'

type Preferences={lexicalRecall:boolean;semanticRecall:boolean;autoCapture:boolean;captureMode:'low_risk'|'propose_only'}
export const memoryDefaults:Preferences={lexicalRecall:true,semanticRecall:false,autoCapture:true,captureMode:'low_risk'}
const preferences=(memory:MemoryStatus):Preferences=>({lexicalRecall:memory.lexicalRecall,semanticRecall:memory.semantic,
  autoCapture:memory.autoCapture,captureMode:memory.captureMode==='propose_only'?'propose_only':'low_risk'})
const same=(a:Preferences,b:Preferences)=>Object.keys(memoryDefaults).every(key=>a[key as keyof Preferences]===b[key as keyof Preferences])

type SideState={busy:boolean;unknown?:boolean;error?:string;done?:'import'|'export'|'access';revision?:number}
export function MemorySettings({view,projects=null,locked=false}:{view:DesktopSessionView|null;projects?:ProjectState|null;locked?:boolean}){
  const {t}=useI18n(),id=useId(),memory=view?.memory
  const scope=`memory:${view?.sessionId}:${view?.workspace}`
  const action=useSettingsAction(scope)
  const [pending,setPending]=useState<Preferences|null>(null)
  const [includeSensitive,setIncludeSensitive]=useState(false)
  const [side,setSide]=useState<SideState>({busy:false})
  const alive=useRef(true),currentScope=useRef(scope),sending=useRef(false)
  currentScope.current=scope
  useEffect(()=>{alive.current=true;return()=>{alive.current=false}},[])
  const confirmed=!!memory&&!!pending&&same(preferences(memory),pending)
  useEffect(()=>{if(confirmed)setPending(null)},[confirmed])
  const waiting=!!action.result&&!!pending&&!confirmed
  const sideWaiting=!!side.revision&&(view?.stateRevision??0)<side.revision
  const disabled=locked||!memory||!view?.status.ready||!view.status.connected||!!view.recovering||!!view.activeTurnId||!!view.activeGenerationId
    ||!!view.approvals.length||!!view.inputs.length||!!memory?.maintenanceBusy||!!projects?.busy||action.busy||waiting||side.busy||sideWaiting||!!side.unknown
  async function save(patch:Partial<Preferences>,reset=false){
    if(disabled||sending.current||!memory)return
    sending.current=true;setSide({busy:false})
    const next=reset?memoryDefaults:{...preferences(memory),...patch};setPending(next)
    try{const result=await action.run(()=>window.api.memoryCommand(reset?'memory_reset_settings':'memory_configure',reset?{}:next));if(!result)setPending(null);else if(reset)setIncludeSensitive(false)}
    finally{sending.current=false}
  }
  async function external(request:()=>Promise<MemoryControlResult>,done:NonNullable<SideState['done']>){
    if(disabled||sending.current)return
    sending.current=true;setSide({busy:true});const origin=scope
    try{
      const result=await request()
      if(!alive.current||currentScope.current!==origin)return
      if(result.canceled){setSide({busy:false});return}
      if(result.completed)setSide({busy:false,done,revision:result.stateRevision})
      else setSide({busy:false,error:result.error?.code||'MEMORY_WRITE_FAILED',unknown:result.error?.outcomeUnknown})
    }catch{if(alive.current&&currentScope.current===origin)setSide({busy:false,error:'MEMORY_OUTCOME_UNKNOWN',unknown:true})}
    finally{sending.current=false}
  }
  const toggle=(field:'lexicalRecall'|'semanticRecall'|'autoCapture',label:string,hint:string,extraDisabled=false)=><input
    id={id+'-'+field} data-memory-setting={field} className="nova-switch" role="switch" type="checkbox" aria-label={label} aria-describedby={hint}
    checked={memory?(field==='semanticRecall'?memory.semantic:memory[field]):false} disabled={disabled||extraDisabled}
    onChange={event=>void save({[field]:event.target.checked})}/>
  const error=side.error||action.errorCode
  const errorKey=error==='MEMORY_IMPORT_INVALID'?'memoryImportInvalid':error==='MEMORY_TRANSFER_TOO_LARGE'?'memoryTransferLarge':error==='MEMORY_EMBEDDING_REQUIRED'?'memorySemanticRequired':
    error==='CONFLICT_ACTIVE_OPERATION'||error==='PROJECT_BUSY'?'memoryBusy':error==='REVISION_CONFLICT'?'memoryStale':'memoryOperationFailed'
  return <div className="nova-memory-settings" aria-busy={disabled}>
    <div className="nova-settings-introduction nova-section-introduction"><div><h2>{t('settingsMemory')}</h2><p>{t('memoryDescription')}</p></div>
      <button className="nova-settings-reset" type="button" disabled={disabled} onClick={()=>void save({},true)}>{t('settingsReset')}</button></div>
    <section className="nova-preferences-group" aria-labelledby={id+'-recall'}><h3 id={id+'-recall'}>{t('memoryRecovery')}</h3>
      <div className="nova-settings-card nova-preferences-list">
        <div className="nova-preference-row"><div><span className="nova-setting-label">{t('memorySettingsLexical')}</span><p id={id+'-lexical-hint'}>{t('memoryLexicalHint')}</p></div>
          {toggle('lexicalRecall',t('memorySettingsLexical'),id+'-lexical-hint')}</div>
        <div className="nova-preference-row"><div><span className="nova-setting-label">{t('memorySettingsSemantic')}</span><p id={id+'-semantic-hint'}>{t('memorySemanticHint')}</p></div>
          {toggle('semanticRecall',t('memorySettingsSemantic'),id+'-semantic-hint',memory?.semanticAvailable!==true)}</div>
      </div>
    </section>
    <section className="nova-preferences-group" aria-labelledby={id+'-records'}><h3 id={id+'-records'}>{t('memoryRecords')}</h3>
      <div className="nova-settings-card nova-preferences-list">
        <div className="nova-preference-row"><div><span className="nova-setting-label">{t('memorySettingsCapture')}</span><p id={id+'-capture-hint'}>{t('memoryCaptureHint')}</p></div>
          {toggle('autoCapture',t('memorySettingsCapture'),id+'-capture-hint')}</div>
        <div className="nova-preference-row"><div><span className="nova-setting-label">{t('memoryCaptureMode')}</span><p>{t('memoryCaptureModeHint')}</p></div>
          <SettingsSelect id={id+'-mode'} data-settings-select="memoryCaptureMode" aria-label={t('memoryCaptureMode')}
            value={memory?.captureMode==='propose_only'?'propose_only':'low_risk'} disabled={disabled||!memory?.autoCapture}
            options={[{value:'low_risk',label:t('memoryLowRisk')},{value:'propose_only',label:t('memoryProposeOnly')}]}
            onChange={value=>void save({captureMode:value as Preferences['captureMode']})}/></div>
        <div className="nova-preference-row"><div><h4>{t('memoryImport')}</h4><p>{t('memoryImportHint')}</p></div>
          <button className="nova-settings-secondary" data-memory-import type="button" disabled={disabled} onClick={()=>void external(()=>window.api.memoryTransfer('import'),'import')}>{t('memoryImportButton')}</button></div>
        <div className="nova-preference-row"><div><h4>{t('memoryExport')}</h4><p>{t('memoryExportHint')}</p></div><div className="nova-memory-controls">
          <span className="settings-toggle-row"><input data-memory-export-sensitive aria-label={t('memoryIncludeSensitive')} type="checkbox" checked={includeSensitive} disabled={disabled} onChange={event=>setIncludeSensitive(event.target.checked)}/>{t('memoryIncludeSensitive')}</span>
          <button className="nova-settings-secondary" data-memory-export type="button" disabled={disabled} onClick={()=>void external(()=>window.api.memoryTransfer('export',includeSensitive),'export')}>{t('memoryExportButton')}</button></div></div>
      </div>
    </section>
    <section className="nova-preferences-group" aria-labelledby={id+'-access'}><h3 id={id+'-access'}>{t('memorySensitiveAccess')}</h3>
      <div className="nova-settings-card nova-preferences-list">{projects?.folders.map(folder=><div className="nova-preference-row nova-project-setting-row" key={folder.path}>
        <div><span className="nova-setting-label">{folder.name}</span><p title={folder.path}>{folder.path}</p></div>
        <input id={id+'-project-'+folder.path} data-memory-project={folder.path} className="nova-switch" role="switch" type="checkbox" aria-label={folder.name}
          checked={!!memory?.sensitiveProjects?.some(path=>sameProjectPath(path,folder.path))} disabled={disabled}
          onChange={event=>{const enabled=event.target.checked;void external(()=>window.api.memoryProjectAccess(folder.path,enabled),'access')}}/>
      </div>)}{!projects?.folders.length&&<p className="settings-hint">{t('projectLoading')}</p>}</div>
    </section>
    {action.unconfirmed||side.unknown?<p className="nova-settings-error" role="alert">{t('memorySettingsUnconfirmed')}</p>:error?<div className="nova-settings-error" role="alert"><p>{t(errorKey)}</p><details><summary>{t('diagnosticDetails')}</summary><code>{error}</code></details></div>:
      side.done?<p className="settings-feedback" role="status">{t(side.done==='import'?'memoryImportDone':side.done==='export'?'memoryExportDone':'settingsSaved')}</p>:
      action.busy||waiting||side.busy||sideWaiting?<p className="settings-feedback" role="status">{t('settingsSaving')}</p>:
      action.result?<p className="settings-feedback" role="status">{t('settingsSaved')}</p>:null}
  </div>
}
