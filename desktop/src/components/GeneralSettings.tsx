import {useId} from 'react'
import {useI18n} from '../i18n'
import {defaultGeneral,type LanguagePreference} from '../../shared/desktop_general'
import {SettingsSelect} from './SettingsSelect'

export function GeneralSettings({titleId}:{titleId:string}){
  const {t,general=defaultGeneral,generalReady=false,generalSaveState='idle',saveGeneral}=useI18n()
  const id=useId(),busy=generalSaveState==='saving'||generalSaveState==='unconfirmed',disabled=busy||!generalReady
  return <div className="nova-general-settings">
    <div className="nova-settings-introduction nova-section-introduction">
      <div><h2 id={titleId}>{t('settingsGeneral')}</h2><p>{t('settingsGeneralHint')}</p></div>
      <button type="button" className="nova-settings-reset" disabled={disabled} onClick={()=>void saveGeneral(defaultGeneral,true)}>{t('settingsReset')}</button>
    </div>
    <section className="nova-preferences-group" aria-labelledby={id+'-interface'}>
      <h3 id={id+'-interface'}>{t('generalInterface')}</h3>
      <div className="nova-settings-card nova-preferences-list" aria-busy={busy}>
        <div className="nova-preference-row"><div><span className="nova-setting-label">{t('generalLanguage')}</span><p id={id+'-language-hint'}>{t('generalLanguageHint')}</p></div>
          <SettingsSelect id={id+'-language'} data-settings-select="language" aria-label={t('generalLanguage')} aria-describedby={id+'-language-hint'}
            value={general.language} disabled={disabled} options={[{value:'system',label:t('generalSystem')},{value:'es',label:'Español'},{value:'en',label:'English'}]}
            onChange={value=>void saveGeneral({...general,language:value as LanguagePreference})}/>
        </div>
        <div className="nova-preference-row"><div><span className="nova-setting-label">{t('generalShowFiles')}</span><p id={id+'-files-hint'}>{t('generalShowFilesHint')}</p></div>
          <input id={id+'-files'} data-general="showFiles" aria-label={t('generalShowFiles')} className="nova-switch" type="checkbox" role="switch" checked={general.showFiles}
            disabled={disabled} aria-describedby={id+'-files-hint'} onChange={event=>void saveGeneral({...general,showFiles:event.target.checked})}/>
        </div>
        <div className="nova-preference-row"><div><span className="nova-setting-label">{t('generalViewSwitch')}</span><p id={id+'-view-hint'}>{t('generalViewSwitchHint')}</p></div>
          <input id={id+'-view'} data-general="autoSwitchView" aria-label={t('generalViewSwitch')} className="nova-switch" type="checkbox" role="switch" checked={general.autoSwitchView}
            disabled={disabled} aria-describedby={id+'-view-hint'} onChange={event=>void saveGeneral({...general,autoSwitchView:event.target.checked})}/>
        </div>
        <div className="nova-preference-row"><div><span className="nova-setting-label">{t('generalTransitions')}</span><p id={id+'-transitions-hint'}>{t('generalTransitionsHint')}</p></div>
          <input id={id+'-transitions'} data-general="transitionsEnabled" aria-label={t('generalTransitions')} className="nova-switch" type="checkbox" role="switch" checked={general.transitionsEnabled}
            disabled={disabled} aria-describedby={id+'-transitions-hint'} onChange={event=>void saveGeneral({...general,transitionsEnabled:event.target.checked})}/>
        </div>
        <div className="nova-preference-row"><div><span className="nova-setting-label">{t('generalSourceContext')}</span><p id={id+'-source-context-hint'}>{t('generalSourceContextHint')}</p></div>
          <input id={id+'-source-context'} data-general="collapsibleSourceContext" aria-label={t('generalSourceContext')} className="nova-switch" type="checkbox" role="switch" checked={general.collapsibleSourceContext}
            disabled={disabled} aria-describedby={id+'-source-context-hint'} onChange={event=>void saveGeneral({...general,collapsibleSourceContext:event.target.checked})}/>
        </div>
      </div>
    </section>
    {generalSaveState!=='idle'&&<p className={generalSaveState==='failed'?'nova-settings-error':busy?'nova-settings-pending':'nova-settings-success'} role={generalSaveState==='failed'?'alert':'status'}>
      {t(generalSaveState==='failed'?'generalSaveFailed':generalSaveState==='saving'?'settingsSaving':generalSaveState==='unconfirmed'?'settingsSaveUnconfirmed':generalSaveState==='reset'?'generalResetDone':'settingsSaved')}</p>}
  </div>
}
