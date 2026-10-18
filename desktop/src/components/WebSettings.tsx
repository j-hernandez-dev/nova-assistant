import {useEffect,useRef,useState,type ReactNode} from 'react'
import type {DesktopSessionView} from '../../shared/application'
import {useI18n} from '../i18n'
import {SettingsActionFeedback,useSettingsAction} from '../settings_actions'

type Props={view:DesktopSessionView|null}
export function WebSettings({view}:Props){
  const {t}=useI18n()
  const scope=`${view?.sessionId||''}:${view?.workspace||''}`
  const disabled=!view?.status.ready||!!view.activeTurnId||!!view.approvals.length||!!view.inputs.length
  return <>
    <ServiceSetting key={`${scope}:fetch`} title={t('settingsFetch')} hint={t('settingsFetchHint')} disabled={disabled}
      effective={view?.fetch?String(view.fetch.enabled):undefined} scope={scope} kind="SetFetchEnabled" field="enabled"
      choices={[['true',t('settingsOn')],['false',t('settingsOff')]]}>
      {view?.fetch&&<ObservedValue label={t('settingsAvailable')} value={t(view.fetch.available?'settingsAvailable':'settingsUnavailable')}/>}
    </ServiceSetting>
    <ServiceSetting key={`${scope}:engine`} title={t('settingsSearchEngine')} disabled={disabled}
      effective={view?.search?.engine} scope={scope} kind="SetSearchEngine" field="engine"
      choices={[['bing','Bing'],['google','Google'],['duckduckgo','DuckDuckGo']]}>
      {view?.search&&<><ObservedValue label={t('settingsObserved')} value={t(view.search.available?'settingsAvailable':'settingsUnavailable')}/>
        {view.search.runtimeCheckedOnUse&&<p className="settings-hint">{t('settingsRuntimeOnUse')}</p>}
        {view.search.unavailableReason&&<SettingsCode code={view.search.unavailableReason}/>}</>}
    </ServiceSetting>
    <ServiceSetting key={`${scope}:browser`} title={t('settingsBrowserAdapter')} hint={t('settingsBrowserChangeHint')} disabled={disabled}
      effective={view?.browser?.selected} scope={scope} kind="SetBrowser" field="browser"
      choices={['webview2','chrome','edge'].map(value=>[value,value==='webview2'?'WebView2':value==='chrome'?'Chrome':'Edge',
        !!view?.browser?.choices.find(choice=>choice.browser===value&&!choice.available)])}>
      {view?.browser&&<><ObservedValue label={t('settingsObserved')} value={t(view.browser.available?'settingsAvailable':'settingsUnavailable')}/>
        {view.browser.runtimeCheckedOnUse&&<p className="settings-hint">{t('settingsRuntimeOnUse')}</p>}
        {view.browser.unavailableReason&&<SettingsCode code={view.browser.unavailableReason}/>}</>}
    </ServiceSetting>
    <p className="settings-hint">{t('settingsNoIsolation')}</p>
  </>
}

export function ServiceSetting({title,hint,effective,scope,kind,field,choices,disabled,children}:{
  title:string;hint?:string;effective:string|undefined;scope:string;kind:string;field:string
  choices:Array<[string,string,boolean?]>;disabled:boolean;children?:ReactNode
}){
  const {t}=useI18n()
  const [draft,setDraft]=useState(effective||'')
  const [submitted,setSubmitted]=useState<string|null>(null)
  const previous=useRef(effective)
  const action=useSettingsAction(scope)
  const waiting=!!action.result?.accepted&&submitted!==null&&effective!==submitted
  useEffect(()=>{setDraft(current=>current===(previous.current||'')?effective||'':current);previous.current=effective},[effective])
  const confirmed=!!action.result&&submitted!==null&&effective===submitted&&draft===submitted
  return <form className="nova-settings-card" aria-label={title} onSubmit={event=>{event.preventDefault();
    if(effective===undefined||draft===effective||disabled||action.busy||waiting)return
    setSubmitted(draft)
    void action.run(()=>window.api.applicationCommand(kind,{[field]:field==='enabled'?draft==='true':draft})).then(receipt=>{
      if(!receipt)setSubmitted(null)
    })
  }}>
    <div className="nova-settings-row"><div><label>{title}</label>{hint&&<p>{hint}</p>}</div>
      <select aria-label={title} value={draft} disabled={disabled||action.busy||waiting||effective===undefined}
        onChange={event=>setDraft(event.target.value)}>
        {!draft&&<option value="">{t('settingsUnknown')}</option>}
        {choices.map(([value,label,unavailable])=><option key={value} value={value} disabled={unavailable&&value!==effective}>{label}{unavailable?` · ${t('settingsUnavailable')}`:''}</option>)}
      </select></div>
    <p className="settings-hint">{t('settingsEffective')}: {choices.find(([value])=>value===effective)?.[1]||t('settingsUnknown')}</p>
    {effective===undefined?<p className="settings-hint">{t('settingsNotObserved')}</p>:children}
    {confirmed?<p className="settings-feedback" role="status">{t('settingsServiceSaved')}</p>:<SettingsActionFeedback action={action}/>}
    <div className="nova-settings-actions">
      <button type="button" className="nova-settings-secondary" disabled={action.busy||waiting||draft===effective} onClick={()=>setDraft(effective||'')}>{t('settingsServiceCancel')}</button>
      <button className="nova-settings-primary" type="submit" disabled={disabled||action.busy||waiting||effective===undefined||draft===effective}>{t('settingsServiceSave')}</button>
    </div>
  </form>
}
export function ObservedValue({label,value}:{label:string;value:string}){
  return <div className="settings-observed-row"><span>{label}</span><strong>{value}</strong></div>
}
export function SettingsCode({code}:{code:string}){
  const {t}=useI18n();return <details className="settings-diagnostics"><summary>{t('diagnosticDetails')}</summary><code>{code}</code></details>
}
