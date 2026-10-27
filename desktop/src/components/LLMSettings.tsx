import {useId,useState} from 'react'
import {useI18n} from '../i18n'
import type {DesktopSessionView} from '../../shared/application'
import type {UsageRange} from '../../shared/model_usage'
import type {ModelVisibilityState} from '../model_visibility'
import {ContextSettings} from './ContextSettings'
import {ModelUsage} from './ModelUsage'
import '../llm_settings.css'

export function LLMSettings({view,models,visibility,active,locked}:{view:DesktopSessionView|null;models:string[];visibility:ModelVisibilityState;active:boolean;locked:boolean}){
  const {t}=useI18n(),id=useId()
  const [range,setRange]=useState<UsageRange>('today'),[reset,setReset]=useState<'idle'|'busy'|'done'|'failed'>('idle'),[contextBusy,setContextBusy]=useState(false)
  const running=!!view?.activeTurnId||!!view?.activeGenerationId||!!view?.approvals.length||!!view?.inputs.length
  const disabled=locked||visibility.busy||!visibility.ready||reset==='busy'
  const status=view?.status
  const inventoryKnown=!!view?.readiness.observedAt&&!['OLLAMA_UNAVAILABLE','READINESS_CHECK_FAILED','READINESS_STALE','CHECKING','BACKEND_DISCONNECTED'].includes(view?.readiness.reason||'')
  async function restore(){
    if(disabled||running||contextBusy||!status?.ready)return
    setReset('busy')
    try{
      const context=await window.api.applicationCommand('SetContextWindow',{requestedTokens:0})
      if(!context.accepted){setReset('failed');return}
      const visible=await visibility.save([])
      if(visible){setRange('today');setReset('done')}else setReset('failed')
    }catch{setReset('failed')}
  }
  return <div className="nova-llm-settings">
    <div className="nova-settings-introduction nova-section-introduction"><div><h2>{t('settingsConnection')}</h2><p>{t('llmHint')}</p></div><button className="nova-settings-reset" type="button" disabled={disabled||running||contextBusy||!status?.ready} onClick={()=>void restore()}>{t('settingsReset')}</button></div>
    <section className="nova-preferences-group" aria-labelledby={id+'-engine'}><h3 id={id+'-engine'}>{t('llmEngine')}</h3>
      <div className="nova-settings-card nova-preferences-list">
        <div className="nova-llm-option"><h4>{t('llmStatus')}</h4>
          <dl className="nova-llm-status"><div><dt>{t('settingsCurrentProvider')}</dt><dd>{status?.provider||t('settingsUnknown')}</dd></div><div><dt>{t('settingsCurrentModel')}</dt><dd>{status?.model||t('settingsUnknown')}</dd></div><div><dt>{t('settingsOllama')}</dt><dd className={view?.readiness.ready?'nova-llm-ready':''}>{t(view?.readiness.ready?'settingsAvailable':'settingsUnavailable')}</dd></div></dl>
        </div>
        <div className="nova-llm-option"><h4>{t('llmUsage')}</h4><ModelUsage active={active&&!!status?.ready} revision={view?.activeTurnId} range={range} onRange={setRange}/></div>
        <div className="nova-llm-option"><ContextSettings view={view} onBusyChange={setContextBusy}/></div>
      </div>
    </section>
    <section className="nova-preferences-group" aria-labelledby={id+'-models'}><h3 id={id+'-models'}>{t('llmModels')}</h3><div className="nova-settings-card nova-preferences-list">
      {models.map(model=><div className="nova-preference-row nova-llm-model" key={model}><span className="nova-setting-label">{model}</span><input className="nova-switch" role="switch" type="checkbox" id={id+'-'+model} data-model-visibility={model} aria-label={model} checked={!visibility.hiddenModels.includes(model)} disabled={disabled} onChange={event=>void visibility.save(event.target.checked?visibility.hiddenModels.filter(name=>name!==model):[...visibility.hiddenModels,model])}/></div>)}
      {!models.length&&<p className="settings-hint">{t(inventoryKnown?'llmModelsEmpty':'llmModelsUnknown')}</p>}
    </div>
      {models.length>0&&models.every(model=>visibility.hiddenModels.includes(model))&&<p className="settings-hint">{t('llmNoVisibleModels')}</p>}
      {visibility.error&&<p className="nova-settings-error" role="alert">{t('llmVisibilityFailed')}</p>}
    </section>
    {(reset==='done'||reset==='failed')&&<p className={reset==='done'?'nova-settings-success':'nova-settings-error'} role={reset==='done'?'status':'alert'}>{t(reset==='done'?'llmResetDone':'llmResetFailed')}</p>}
  </div>
}
