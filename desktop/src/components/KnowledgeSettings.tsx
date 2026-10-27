import {useEffect,useId,useRef,useState} from 'react'
import type {DesktopSessionView,KnowledgePreferences} from '../../shared/application'
import {useI18n} from '../i18n'
import {useSettingsAction} from '../settings_actions'

const defaults:KnowledgePreferences={lexicalRecall:true,semanticRecall:false,autoIndex:true,autoRebuild:true}
const values=(state:KnowledgePreferences):KnowledgePreferences=>({lexicalRecall:state.lexicalRecall,semanticRecall:state.semanticRecall,autoIndex:state.autoIndex,autoRebuild:state.autoRebuild})
const matches=(a:KnowledgePreferences,b:KnowledgePreferences)=>Object.keys(defaults).every(key=>a[key as keyof KnowledgePreferences]===b[key as keyof KnowledgePreferences])

export function KnowledgeSettings({view,locked=false}:{view:DesktopSessionView|null;locked?:boolean}){
  const {t}=useI18n(),id=useId(),state=view?.knowledgeSettings
  const action=useSettingsAction('knowledge:'+view?.sessionId+':'+view?.workspace)
  const [pending,setPending]=useState<KnowledgePreferences|null>(null),sending=useRef(false)
  const confirmed=!!state&&!!pending&&matches(state,pending)
  useEffect(()=>{if(confirmed)setPending(null)},[confirmed])
  const waiting=!!action.result&&!!pending&&!confirmed
  const disabled=locked||!state||!view?.status.ready||!view.status.connected||!!view.recovering||!!view.gap||
    !!view.activeTurnId||!!view.activeGenerationId||!!view.approvals.length||!!view.inputs.length||!!view.memory?.maintenanceBusy||
    !!view.knowledge?.closing||!!view.knowledgeOperations?.some(op=>['running','requested','pending'].includes(op.status))||action.busy||waiting
  async function save(patch:Partial<KnowledgePreferences>,reset=false){
    if(disabled||sending.current||!state)return
    sending.current=true
    const next=reset?defaults:{...values(state),...patch}
    setPending(next)
    try{const result=await action.run(()=>window.api.applicationCommand(reset?'ResetKnowledgeSettings':'SetKnowledgeSettings',reset?{}:next));if(!result)setPending(null)}
    finally{sending.current=false}
  }
  const toggle=(field:keyof KnowledgePreferences,label:string,hint:string,requiresEM=false)=><input id={id+'-'+field}
    type="checkbox" role="switch" className="nova-switch" data-knowledge-setting={field} aria-label={label} aria-describedby={hint}
    checked={state?.[field]??defaults[field]} disabled={disabled||(requiresEM&&!state?.semanticAvailable)}
    onChange={event=>void save({[field]:event.target.checked})}/>
  const row=(field:keyof KnowledgePreferences,label:'knowledgeLexical'|'knowledgeSemantic'|'knowledgeAutoIndex'|'knowledgeAutoRebuild',
    hint:'knowledgeLexicalHint'|'knowledgeSemanticHint'|'knowledgeAutoIndexHint'|'knowledgeAutoRebuildHint',requiresEM=false)=><div className="nova-preference-row">
    <div><span className="nova-setting-label">{t(label)}</span><p id={id+'-'+field+'-hint'}>{t(hint)}{requiresEM?' '+t('knowledgeEmbeddingRequired'):''}</p></div>
    {toggle(field,t(label),id+'-'+field+'-hint',requiresEM)}</div>
  const error=action.errorCode||state?.errorCode
  const errorKey=error==='KNOWLEDGE_EMBEDDING_REQUIRED'?'knowledgeEmbeddingRequired':error==='KNOWLEDGE_EMBEDDING_CONTEXT_EXCEEDED'?'knowledgeContextExceeded':
    error==='REVISION_CONFLICT'?'memoryStale':['PROJECT_BUSY','CONFLICT_ACTIVE_OPERATION'].includes(error||'')?'memoryBusy':'knowledgeOperationFailed'
  return <div className="nova-knowledge-settings" aria-busy={action.busy||waiting}>
    <div className="nova-settings-introduction nova-section-introduction"><div><h2>{t('settingsKnowledge')}</h2><p>{t('settingsKnowledgeHint')}</p></div>
      <button className="nova-settings-reset" type="button" disabled={disabled} onClick={()=>void save({},true)}>{t('settingsReset')}</button></div>
    <p className="settings-feedback">{t('knowledgeExplicitHint')}</p>
    <section className="nova-preferences-group" aria-labelledby={id+'-recall'}><h3 id={id+'-recall'}>{t('knowledgeRecovery')}</h3>
      <div className="nova-settings-card nova-preferences-list">
        {row('lexicalRecall','knowledgeLexical','knowledgeLexicalHint')}
        {row('semanticRecall','knowledgeSemantic','knowledgeSemanticHint',true)}
      </div></section>
    <section className="nova-preferences-group" aria-labelledby={id+'-index'}><h3 id={id+'-index'}>{t('knowledgeIndex')}</h3>
      <div className="nova-settings-card nova-preferences-list">
        {row('autoIndex','knowledgeAutoIndex','knowledgeAutoIndexHint',true)}
        {row('autoRebuild','knowledgeAutoRebuild','knowledgeAutoRebuildHint',true)}
      </div></section>
    {action.unconfirmed?<p className="nova-settings-error" role="status">{t('settingsServiceUnknown')}</p>:
      error?<div className="nova-settings-error" role="alert"><p>{t(errorKey)}</p><details><summary>{t('diagnosticDetails')}</summary><code>{error}</code></details></div>:
      action.busy||waiting?<p className="settings-feedback" role="status">{t('settingsSaving')}</p>:
      action.result?<p className="settings-feedback" role="status">{t('settingsSaved')}</p>:null}
    {state?.indexing&&state.indexedSources<state.totalSources&&<p className="settings-feedback" role="status">{t('knowledgeIndexProgress')} {state.indexedSources}/{state.totalSources}</p>}
  </div>
}
