import {useEffect,useId,useRef,useState,type CSSProperties} from 'react'
import type {DesktopSessionView,EmbeddingStatus,InstalledModel} from '../../shared/application'
import type {UsageRange} from '../../shared/model_usage'
import {useI18n} from '../i18n'
import {useSettingsAction} from '../settings_actions'
import {SettingsSelect} from './SettingsSelect'
import {ModelUsage} from './ModelUsage'
import '../llm_settings.css'

export const EMBEDDING_CONTEXT_PRESETS=[512,1024,2048,4096,8192,16384,32768] as const
type Preferences=Pick<EmbeddingStatus,'modelId'|'requestedTokens'|'enabledModels'>
const preferences=(state:EmbeddingStatus):Preferences=>({modelId:state.modelId,requestedTokens:state.requestedTokens,enabledModels:state.enabledModels})
const same=(a:Preferences,b:Preferences)=>a.modelId===b.modelId&&a.requestedTokens===b.requestedTokens&&a.enabledModels.length===b.enabledModels.length&&a.enabledModels.every(n=>b.enabledModels.includes(n))
const tokens=(n:number)=>n<1024?String(n):`${n/1024}K`

export function EmbeddingSettings({view,models,active,locked}:{view:DesktopSessionView|null;models:InstalledModel[];active:boolean;locked:boolean}){
  const {t}=useI18n(),id=useId(),state=view?.embedding
  const action=useSettingsAction(`embedding:${view?.sessionId}:${view?.workspace}`)
  const [range,setRange]=useState<UsageRange>('today')
  const [contextDraft,setContextDraft]=useState(state?.requestedTokens??0)
  const [pending,setPending]=useState<Preferences|null>(null)
  const contextDraftRef=useRef(contextDraft)
  const submitted=useRef<Preferences|null>(null),sending=useRef(false)
  useEffect(()=>{const next=state?.requestedTokens??0;setContextDraft(next);contextDraftRef.current=next},[state?.requestedTokens,state?.selectedModel,view?.sessionId,view?.workspace])
  useEffect(()=>{setPending(null)},[view?.sessionId,view?.workspace])
  useEffect(()=>{if(action.result&&pending&&state&&same(preferences(state),pending))setPending(null)},[action.result,pending,state])
  const waiting=!!action.result&&!!pending&&!!state&&!same(preferences(state),pending)
  const running=!!view?.activeTurnId||!!view?.activeGenerationId||!!view?.approvals.length||!!view?.inputs.length
  const disabled=locked||!state||!view?.status.ready||!view.status.connected||!!view.recovering||running||action.busy||waiting
  const available=!!state?.connected&&models.length>0
  const selected=models.find(m=>m.name===state?.selectedModel)
  const enabled=models.filter(m=>state?.enabledModels.includes(m.name))
  const controlsDisabled=disabled||!available||!selected
  const selectedContext=contextDraft||state?.selectedTokens||8192
  const contextIndex=Math.max(0,EMBEDDING_CONTEXT_PRESETS.indexOf(selectedContext as typeof EMBEDDING_CONTEXT_PRESETS[number]))
  async function save(next:Preferences,reset=false){
    if(disabled||sending.current)return
    sending.current=true;submitted.current=next;setPending(next)
    try {
      const result=await action.run(()=>window.api.applicationCommand(reset?'ResetEmbeddingSettings':'SetEmbeddingSettings',reset?{}:next))
      if(!result)setPending(null)
      return result
    }
    finally {sending.current=false}
  }
  async function saveContext(next:number){
    if(controlsDisabled||sending.current||!state||next===state.requestedTokens)return
    contextDraftRef.current=next;setContextDraft(next)
    const result=await save({...preferences(state),requestedTokens:next})
    if(!result){contextDraftRef.current=state.requestedTokens;setContextDraft(state.requestedTokens)}
  }
  function toggle(model:string,on:boolean){
    if(!state)return
    const next=on?[...state.enabledModels,model]:state.enabledModels.filter(n=>n!==model)
    const current=next.includes(state.selectedModel)?state.selectedModel:models.find(m=>next.includes(m.name))?.name||''
    void save({...preferences(state),enabledModels:next,modelId:current})
  }
  const error=action.errorCode||state?.errorCode
  const errorModel=action.errorCode?submitted.current?.modelId:state?.selectedModel
  const errorLimit=action.errorCode?models.find(model=>model.name===errorModel)?.contextLength:state?.contextLimit
  const errorKey=error==='EMBEDDING_CONTEXT_LIMIT_EXCEEDED'?'emContextLimitError'
    :error==='EMBEDDING_MEMORY_INSUFFICIENT'?'emMemoryError'
    :error==='EMBEDDING_TIMEOUT'?'emTimeoutError'
    :error==='EMBEDDING_MODEL_UNAVAILABLE'?'emModelError'
    :error==='EMBEDDING_CONNECTION_FAILED'?'emConnectionError'
    :error==='CONFLICT_ACTIVE_OPERATION'||error==='PROJECT_BUSY'?'contextBusy'
    :error==='REVISION_CONFLICT'?'contextRevisionError':'emSaveError'
  return <div className="nova-llm-settings nova-em-settings" aria-busy={action.busy||waiting}>
    <div className="nova-settings-introduction nova-section-introduction"><div><h2>{t('settingsEmbedding')}</h2><p>{t('emHint')}</p></div><button className="nova-settings-reset" type="button" disabled={disabled} onClick={()=>void save({modelId:'',requestedTokens:0,enabledModels:models.map(model=>model.name)},true)}>{t('settingsReset')}</button></div>
    <section className="nova-preferences-group" aria-labelledby={id+'-engine'}><h3 id={id+'-engine'}>{t('llmEngine')}</h3>
      <div className="nova-settings-card nova-preferences-list">
        <div className="nova-preference-row nova-em-selection"><div><span className="nova-setting-label">{t('emModel')}</span><p className="settings-hint">{t('emModelHint')}</p></div>
          <SettingsSelect id={id+'-model'} data-settings-select="embeddingModel" aria-label={t('emModel')} value={state?.selectedModel||''} disabled={disabled||!available||!enabled.length}
            options={enabled.length?enabled.map(m=>({value:m.name,label:m.name})):[{value:'',label:t(available?'emNoEnabledModels':'emModelsEmpty'),disabled:true}]}
            onChange={modelId=>state&&void save({...preferences(state),modelId})}/>
        </div>
        <div className="nova-llm-option" aria-disabled={controlsDisabled}><h4>{t('llmStatus')}</h4>
          <dl className="nova-llm-status"><div><dt>{t('settingsCurrentProvider')}</dt><dd>Ollama</dd></div><div><dt>{t('settingsCurrentModel')}</dt><dd>{state?.selectedModel||t('emNoEnabledModels')}</dd></div><div><dt>{t('settingsOllama')}</dt><dd className={state?.connected?'nova-llm-ready':''}>{t(state?.connected?'settingsAvailable':'settingsUnavailable')}</dd></div></dl>
        </div>
        <div className="nova-llm-option" aria-disabled={controlsDisabled}><h4>{t('llmUsage')}</h4><ModelUsage kind="embedding" active={active&&!controlsDisabled} disabled={controlsDisabled} revision={view?.activeTurnId} range={range} onRange={setRange}/></div>
        <div className="nova-llm-option" aria-disabled={controlsDisabled}><div className="nova-context-settings">
          <div className="nova-context-heading"><span className="nova-setting-label">{t('contextTokens')}</span><output htmlFor={id+'-context'}>{contextDraft===0?t('contextAuto'):tokens(contextDraft)}</output></div>
          <p className="settings-hint" id={id+'-context-hint'}>{t('emContextHint')}</p>
          <span className="settings-toggle-row"><input id={id+'-context-auto'} data-embedding-context-auto aria-label={t('contextAutomatic')} type="checkbox" checked={contextDraft===0} disabled={controlsDisabled} onChange={event=>void saveContext(event.target.checked?0:EMBEDDING_CONTEXT_PRESETS[contextIndex])}/>{t('contextAutomatic')}</span>
          <input id={id+'-context'} data-embedding-context aria-label={t('contextTokens')} className="nova-context-slider" type="range" min="0" max={EMBEDDING_CONTEXT_PRESETS.length-1} step="1" value={contextIndex} disabled={controlsDisabled||contextDraft===0}
            aria-describedby={id+'-context-hint'} aria-valuetext={tokens(EMBEDDING_CONTEXT_PRESETS[contextIndex])} style={{'--context-fill':`${contextIndex/(EMBEDDING_CONTEXT_PRESETS.length-1)*100}%`} as CSSProperties}
            onChange={event=>{const next=EMBEDDING_CONTEXT_PRESETS[Number(event.target.value)];contextDraftRef.current=next;setContextDraft(next)}}
            onPointerUp={()=>void saveContext(contextDraftRef.current)} onKeyUp={event=>{if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End','PageUp','PageDown'].includes(event.key))void saveContext(contextDraftRef.current)}} onBlur={()=>void saveContext(contextDraftRef.current)}/>
          <div className="nova-context-ticks" aria-label={t('contextPresets')}>{EMBEDDING_CONTEXT_PRESETS.map((value,position)=><button key={value} type="button" disabled={controlsDisabled} style={{'--context-position':`${position/(EMBEDDING_CONTEXT_PRESETS.length-1)*100}%`} as CSSProperties} aria-pressed={contextDraft===value} onClick={()=>void saveContext(value)}>{tokens(value)}</button>)}</div>
          {!!state?.selectedTokens&&<p className="settings-hint">{t('emContextSelected')}: <strong>{tokens(state.selectedTokens)}</strong></p>}
        </div>
        </div>
      </div>
    </section>
    <section className="nova-preferences-group" aria-labelledby={id+'-models'}><h3 id={id+'-models'}>{t('llmModels')}</h3><div className="nova-settings-card nova-preferences-list">
      {models.map(model=><div className="nova-preference-row nova-llm-model" key={model.name}><span className="nova-setting-label">{model.name}</span><input className="nova-switch" role="switch" type="checkbox" id={id+'-'+model.name} data-embedding-visibility={model.name} aria-label={model.name} checked={!!state?.enabledModels.includes(model.name)} disabled={disabled||!available} onChange={event=>toggle(model.name,event.target.checked)}/></div>)}
      {!models.length&&<p className="settings-hint">{t(state?.connected?'emModelsEmpty':'llmModelsUnknown')}</p>}
    </div>{available&&!enabled.length&&<p className="settings-hint">{t('emEnableHint')}</p>}</section>
    {error&&<div className="nova-settings-error" role="alert"><p>{t(errorKey)}</p>{error==='EMBEDDING_CONTEXT_LIMIT_EXCEEDED'&&!!errorLimit&&<p>{t('emReportedLimit')} ({errorModel}): {tokens(errorLimit)} {t('llmTokens').toLowerCase()}</p>}<details><summary>{t('diagnosticDetails')}</summary><code>{error}</code></details></div>}
    {action.unconfirmed&&<p className="nova-settings-error" role="status">{t('settingsSaveUnconfirmed')}</p>}
    {action.result&&!error&&<p className="nova-settings-success" role="status">{t(waiting?'settingsSaving':'settingsSaved')}</p>}
  </div>
}
