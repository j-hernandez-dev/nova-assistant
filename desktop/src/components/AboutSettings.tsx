import type {ReactNode} from 'react'
import type {AppStatus} from '../types'
import {useI18n,type TranslationKey} from '../i18n'
import {ObservedValue} from './WebSettings'
import {NovaIcon} from './NovaIcon'
import '../about.css'

const descriptions:Record<string,TranslationKey>={
  bash:'aboutToolTerminal',shell:'aboutToolTerminal',run_command:'aboutToolTerminal',exec_command:'aboutToolTerminal',
  read:'aboutToolRead',read_file:'aboutToolRead',write:'aboutToolWrite',write_file:'aboutToolWrite',
  source_read:'aboutToolSourceRead',
  edit:'aboutToolEdit',apply_patch:'aboutToolEdit',glob:'aboutToolFind',list_files:'aboutToolFind',list_dir:'aboutToolFind',
  grep:'aboutToolSearch',search_code:'aboutToolSearch',web_fetch:'aboutToolFetch',web_search:'aboutToolWebSearch',
  todo_write:'aboutToolTasks',ask_user:'aboutToolQuestion',agent:'aboutToolAgent',
  browser_navigate:'aboutToolNavigate',browser_observe:'aboutToolObserve',browser_click:'aboutToolClick',
  browser_type:'aboutToolType',browser_press_key:'aboutToolKey',browser_back:'aboutToolBack',browser_forward:'aboutToolForward',
  browser_reload:'aboutToolReload',browser_close:'aboutToolClose',browser_request_takeover:'aboutToolTakeover',
  browser_upload:'aboutToolUpload',browser_download:'aboutToolDownload',
}

export function AboutSettings({titleId,version,children}:{titleId:string;version:string|null;children?:ReactNode}){
  const {t}=useI18n()
  return <div className="nova-about-settings">
    <div className="nova-settings-introduction"><h2 id={titleId}>{t('settingsAbout')}</h2><p>{t('settingsAboutHint')}</p></div>
    <section className="nova-settings-card nova-about-identity" aria-label="Nova">
      <h3>Nova</h3><p className="nova-about-description">{t('aboutDescription')}</p>
      <ObservedValue label={t('settingsDesktopVersion')} value={version===null?t('checking'):version?'v'+version:t('settingsVersionUnavailable')}/>
      <ObservedValue label={t('aboutCopyright')} value="© 2026 Nova Assistant"/>
    </section>
    {children}
  </div>
}

export function AboutRuntime({status}:{status:AppStatus}){
  const {t,locale}=useI18n()
  const tools=status.tools
  return <section className="nova-settings-card nova-about-runtime" aria-label={t('aboutStatus')}>
    <h3>{t('aboutStatus')}</h3>
    <ObservedValue label={t('backend')} value={t(status.connected?'settingsAvailable':'settingsUnavailable')}/>
    <ObservedValue label={t('provider')} value={status.provider||t('settingsUnknown')}/>
    <ObservedValue label={t('tools')} value={new Intl.NumberFormat(locale).format(tools.length)}/>
    <details className="nova-about-tools">
      <summary><span>{t('aboutShowTools')}</span><NovaIcon name="chevron" size={17}/></summary>
      {tools.length?<ul>{tools.map((name,index)=><li key={name+':'+index}><code>{name}</code>
        <p>{t(Object.prototype.hasOwnProperty.call(descriptions,name)?descriptions[name]:'aboutToolOther')}</p></li>)}</ul>
        :<p className="nova-about-empty" role="status">{t('aboutNoTools')}</p>}
    </details>
  </section>
}
