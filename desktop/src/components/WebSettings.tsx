import {useId,useState} from 'react'
import type {DesktopSessionView} from '../../shared/application'
import {useI18n} from '../i18n'
import {SettingsActionFeedback,useSettingsAction} from '../settings_actions'
import {SettingsSelect} from './SettingsSelect'

type WebPreferences={fetchEnabled:boolean;searchEnabled:boolean;browserEnabled:boolean;engine:string;browser:string}
export const defaultWebPreferences:WebPreferences={fetchEnabled:true,searchEnabled:true,browserEnabled:true,engine:'google',browser:'webview2'}
export function observedWebPreferences(view:DesktopSessionView|null):WebPreferences|null{
  if(!view?.fetch || !view.search || !view.browser)return null
  const value={fetchEnabled:view.fetch.enabled,searchEnabled:view.search.enabled,browserEnabled:view.browser.enabled,
    engine:view.search.engine,browser:view.browser.selected}
  return ['fetchEnabled','searchEnabled','browserEnabled'].every(key=>typeof value[key as keyof WebPreferences]==='boolean')?value:null
}
export function WebSettings({view}:{view:DesktopSessionView|null}){
  const {t}=useI18n(),id=useId()
  const scope=`${view?.sessionId||''}:${view?.workspace||''}`
  const action=useSettingsAction(scope)
  const [submitted,setSubmitted]=useState<WebPreferences|null>(null)
  const current=observedWebPreferences(view)
  const confirmed=!!submitted&&!!current&&Object.keys(defaultWebPreferences).every(key=>current[key as keyof WebPreferences]===submitted[key as keyof WebPreferences])
  const waiting=!!action.result?.accepted&&!!submitted&&!confirmed
  const busy=action.busy||waiting
  const disabled=busy||!current||!view?.status.ready||!view.status.connected||!!view.recovering||!!view.activeTurnId||!!view.approvals.length||!!view.inputs.length
  const save=(patch:Partial<WebPreferences>)=>{
    if(disabled||!current)return
    const value={...current,...patch}
    setSubmitted(value)
    void action.run(()=>window.api.applicationCommand('SetWebSettings',value))
  }
  const toggle=(field:'fetchEnabled'|'searchEnabled'|'browserEnabled',label:string,hint:string)=>
    <input id={id+'-'+field} data-web-permission={field} className="nova-switch" type="checkbox" role="switch"
      aria-label={label} aria-describedby={hint} checked={current?.[field]??false} disabled={disabled}
      onChange={event=>save({[field]:event.target.checked})}/>
  return <div className="nova-web-settings">
    <div className="nova-settings-introduction nova-section-introduction">
      <div><h2>{t('settingsWeb')}</h2><p>{t('settingsWebHint')}</p></div>
      <button type="button" className="nova-settings-reset" disabled={disabled} onClick={()=>save(defaultWebPreferences)}>{t('settingsReset')}</button>
    </div>
    <section className="nova-preferences-group" aria-labelledby={id+'-permissions'}>
      <h3 id={id+'-permissions'}>{t('webPermissions')}</h3>
      <div className="nova-settings-card nova-preferences-list" aria-busy={busy}>
        <div className="nova-preference-row"><div><span className="nova-setting-label">{t('settingsFetch')}</span><p id={id+'-fetch-hint'}>{t('settingsFetchHint')}</p></div>
          <div className="nova-web-controls">{toggle('fetchEnabled',t('settingsFetch'),id+'-fetch-hint')}</div>
        </div>
        <div className="nova-preference-row"><div><span className="nova-setting-label">{t('webSearchPermission')}</span><p id={id+'-search-hint'}>{t('webSearchPermissionHint')}</p></div>
          <div className="nova-web-controls">
            <SettingsSelect data-settings-select="web-search-engine" aria-label={t('settingsSearchEngine')} value={current?.engine||''}
              disabled={disabled||!current?.searchEnabled} options={[{value:'google',label:'Google'},{value:'bing',label:'Bing'},{value:'duckduckgo',label:'DuckDuckGo'}]}
              onChange={engine=>save({engine})}/>
            {toggle('searchEnabled',t('webSearchPermission'),id+'-search-hint')}
          </div>
        </div>
        <div className="nova-preference-row"><div><span className="nova-setting-label">{t('webBrowserPermission')}</span><p id={id+'-browser-hint'}>{t('webBrowserPermissionHint')}</p></div>
          <div className="nova-web-controls">
            <SettingsSelect data-settings-select="web-browser" aria-label={t('settingsBrowserAdapter')} value={current?.browser||''}
              disabled={disabled||!current?.browserEnabled} options={(['webview2','chrome','edge'] as const).map(value=>{
                const unavailable=!!view?.browser?.choices.find(choice=>choice.browser===value&&!choice.available)
                return {value,label:value==='webview2'?'WebView2':value==='chrome'?'Chrome':'Edge',description:unavailable?t('settingsUnavailable'):undefined,disabled:unavailable&&value!==current?.browser}
              })} onChange={browser=>save({browser})}/>
            {toggle('browserEnabled',t('webBrowserPermission'),id+'-browser-hint')}
          </div>
        </div>
      </div>
    </section>
    {!current&&<p className="settings-hint">{t('settingsNotObserved')}</p>}
    {confirmed&&action.result?<p className="settings-feedback" role="status">{t('settingsSaved')}</p>:waiting?<p className="settings-feedback" role="status">{t('settingsSaving')}</p>:<SettingsActionFeedback action={action}/>}
    <p className="settings-hint nova-web-notice">{t('settingsNoIsolation')}</p>
  </div>
}

export function ObservedValue({label,value}:{label:string;value:string}){
  return <div className="settings-observed-row"><span>{label}</span><strong>{value}</strong></div>
}
export function SettingsCode({code}:{code:string}){
  const {t}=useI18n();return <details className="settings-diagnostics"><summary>{t('diagnosticDetails')}</summary><code>{code}</code></details>
}
