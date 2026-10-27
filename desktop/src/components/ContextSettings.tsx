import {useEffect,useId,useRef,useState,type CSSProperties} from 'react'
import type {DesktopSessionView} from '../../shared/application'
import {useI18n} from '../i18n'
import {useSettingsAction} from '../settings_actions'
export const CONTEXT_PRESETS=[4096,8192,16384,32768,65536,131072,262144] as const
const label=(tokens:number)=>`${tokens/1024}K`

/** Each control saves through Application; confirmed context remains the authority. */
export function ContextSettings({view,onBusyChange}:{view:DesktopSessionView|null;onBusyChange?:(value:boolean)=>void}){
  const {t}=useI18n(),id=useId(),context=view?.context,requested=context?.requestedTokens
  const [draft,setDraft]=useState(requested??0)
  const draftRef=useRef(draft),submitted=useRef<number|null>(null)
  const submitting=useRef(false)
  const action=useSettingsAction(`context:${view?.sessionId}`)
  const waiting=!!action.result&&submitted.current!==null&&requested!==submitted.current
  useEffect(()=>{if(requested!==undefined){setDraft(requested);draftRef.current=requested}},[requested])
  useEffect(()=>{onBusyChange?.(action.busy||waiting)},[action.busy,waiting,onBusyChange])
  const unavailable=!context||!view?.status.ready||!!view?.recovering
  const running=!!view?.activeTurnId||!!view?.activeGenerationId||!!view?.approvals.length||!!view?.inputs.length
  const disabled=unavailable||running||action.busy||waiting
  const selected=draft||context?.selectedTokens||8192
  const index=Math.max(0,CONTEXT_PRESETS.indexOf(selected as typeof CONTEXT_PRESETS[number]))
  async function save(next:number){
    if(disabled||submitting.current||next===requested)return
    submitting.current=true
    submitted.current=next;draftRef.current=next;setDraft(next)
    const result=await action.run(()=>window.api.applicationCommand('SetContextWindow',{requestedTokens:next}))
    submitting.current=false
    if(result===null&&!action.unconfirmed){setDraft(requested??0);draftRef.current=requested??0}
  }
  const error=action.errorCode||context?.errorCode
  const errorKey=error==='CONTEXT_LIMIT_EXCEEDED'||error==='CONTEXT_UNSUPPORTED'?'contextLimitError'
    :error==='CONTEXT_PREFERENCES_SAVE_FAILED'?'contextSaveError'
    :error==='CONFLICT_ACTIVE_OPERATION'||error==='PROJECT_BUSY'?'contextBusy'
    :error==='REVISION_CONFLICT'?'contextRevisionError':'contextOperationError'
  return <div className="nova-context-settings" aria-busy={action.busy||waiting}>
    <div className="nova-context-heading"><span className="nova-setting-label">{t('contextTokens')}</span><output htmlFor={id}>{draft===0?t('contextAuto'):label(draft)}</output></div>
    <p className="settings-hint" id={id+'-hint'}>{t('contextTokensHint')}</p>
    <span className="settings-toggle-row"><input id={id+'-auto'} aria-label={t('contextAutomatic')} type="checkbox" checked={draft===0} disabled={disabled} onChange={event=>void save(event.target.checked?0:CONTEXT_PRESETS[index])}/>{t('contextAutomatic')}</span>
    <input id={id} aria-label={t('contextTokens')} className="nova-context-slider" type="range" min="0" max={CONTEXT_PRESETS.length-1} step="1" value={index} disabled={disabled||draft===0}
      aria-describedby={id+'-hint'} aria-valuetext={label(CONTEXT_PRESETS[index])} style={{'--context-fill':`${index/(CONTEXT_PRESETS.length-1)*100}%`} as CSSProperties}
      onChange={event=>{const next=CONTEXT_PRESETS[Number(event.target.value)];draftRef.current=next;setDraft(next)}}
      onPointerUp={()=>void save(draftRef.current)} onKeyUp={event=>{if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End','PageUp','PageDown'].includes(event.key))void save(draftRef.current)}} onBlur={()=>void save(draftRef.current)}/>
    <div className="nova-context-ticks" aria-label={t('contextPresets')}>{CONTEXT_PRESETS.map((tokens,position)=><button key={tokens} type="button" disabled={disabled} style={{'--context-position':`${position/(CONTEXT_PRESETS.length-1)*100}%`} as CSSProperties} aria-pressed={draft===tokens} onClick={()=>void save(tokens)}>{label(tokens)}</button>)}</div>
    {context?.selectedTokens&&<p className="settings-hint">{t('contextSelected')}: <strong>{label(context.selectedTokens)}</strong></p>}
    {unavailable&&<p className="settings-hint" role="status">{t('settingsControlsUnavailable')}</p>}
    {running&&<p className="settings-hint" role="status">{t('contextBusy')}</p>}
    {error&&<p className="nova-settings-error" role="alert">{t(errorKey)}</p>}
    {action.unconfirmed&&<p className="nova-settings-error" role="status">{t('settingsSaveUnconfirmed')}</p>}
    {action.result&&submitted.current===draft&&<p className="nova-settings-success" role="status">{t(waiting?'contextApplying':'contextSaved')}</p>}
  </div>
}
