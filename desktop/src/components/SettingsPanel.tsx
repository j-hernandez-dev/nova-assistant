import { useState, useEffect, useId, type ReactNode } from 'react'
import { ModalHost } from './ModalHost'
import { AppearanceSettings } from './AppearanceSettings'
import { ShortcutSettings } from './ShortcutSettings'
import { NovaIcon } from './NovaIcon'
import { useI18n } from '../i18n'
import { GeneralSettings } from './GeneralSettings'
import {AboutSettings} from './AboutSettings'
import '../settings.css'

export type SettingsSection = 'general' | 'appearance' | 'chat' | 'connection' | 'embedding' | 'projects' | 'web' | 'memory' | 'storage' | 'knowledge' | 'shortcuts' | 'about'

type Props = {
  open?: boolean
  backendLocked?: boolean
  onClose: () => void
  onSectionChange?: (section:SettingsSection)=>void
  initialSection?: SettingsSection
  chat?: ReactNode
  connection?: ReactNode
  embedding?: ReactNode
  projects?: ReactNode
  web?: ReactNode
  memory?: ReactNode
  storage?: ReactNode
  knowledge?: ReactNode
  about?: ReactNode
}

const sections = [
  ['general', 'settingsGeneral', 'settingsGeneralHint'],
  ['appearance', 'settingsAppearance', 'settingsAppearanceHint'],
  ['connection', 'settingsConnection', 'settingsConnectionHint'],
  ['embedding', 'settingsEmbedding', 'emHint'],
  ['projects', 'settingsProjects', 'settingsProjectsHint'],
  ['chat', 'settingsChat', 'settingsChatHint'],
  ['web', 'settingsWeb', 'settingsWebHint'],
  ['memory', 'settingsMemory', 'settingsMemoryHint'],
  ['storage', 'settingsStorage', 'settingsStorageHint'],
  ['knowledge', 'settingsKnowledge', 'settingsKnowledgeHint'],
  ['shortcuts', 'settingsShortcuts', 'settingsShortcutsHint'],
  ['about', 'settingsAbout', 'settingsAboutHint'],
] as const

const sectionGroups = [
  {id:'interface',label:'settingsGroupInterface',sections:['general','appearance','shortcuts']},
  {id:'models',label:'settingsGroupModels',sections:['connection','embedding']},
  {id:'context',label:'settingsGroupContext',sections:['memory','knowledge','web']},
  {id:'data',label:'settingsGroupData',sections:['projects','chat','storage']},
] as const

export function SettingsPanel({ onClose, onSectionChange, open = true, initialSection = 'general', backendLocked = false, chat, connection, embedding, projects, web, memory, storage, knowledge, about }: Props) {
  const { t } = useI18n()
  const [section, setSection] = useState<SettingsSection>(initialSection)
  const [appVersion, setAppVersion] = useState<string | null>(null)
  const titleId = useId()
  const sectionTitleId = useId()
  const appearanceTitleId = useId()
  const locked = (name: string) => backendLocked && !['general', 'appearance', 'shortcuts', 'about'].includes(name)
  useEffect(() => { if (backendLocked && !['general', 'appearance', 'shortcuts', 'about'].includes(section)) {setSection('general');onSectionChange?.('general')} }, [backendLocked,section,onSectionChange])

  useEffect(() => {
    let current = true
    const timer = setTimeout(() => { if (current) setAppVersion('') }, 15000)
    const api = typeof window === 'undefined' ? undefined : window.api
    if (typeof api?.getAppVersion === 'function') {
      void api.getAppVersion().then(version => {
        if (current) setAppVersion(typeof version === 'string' ? version : '')
      }).catch(() => { if (current) setAppVersion('') }).finally(() => clearTimeout(timer))
    } else { setAppVersion(''); clearTimeout(timer) }
    return () => { current = false; clearTimeout(timer) }
  }, [])

  const slots = { appearance: <AppearanceSettings titleId={appearanceTitleId} active={open && section === 'appearance'} />, chat, connection, embedding, projects, web, memory, storage, knowledge }
  const selected = sections.find(([id]) => id === section) || sections[0]
  const sectionButton = (id:SettingsSection) => {
    const entry=sections.find(([key])=>key===id)!
    return <button key={id} type="button" data-settings-section={id} aria-current={section===id?'page':undefined}
      disabled={locked(id)} title={locked(id)?t('modelDownloadBusy'):undefined}
      onClick={()=>{setSection(id);onSectionChange?.(id)}}><SettingsIcon name={id}/><span>{t(entry[1])}</span></button>
  }

  return <ModalHost open={open} onClose={onClose} labelledBy={titleId} className="nova-settings-dialog nova-surface-dialog">
    <header className="nova-settings-header nova-surface-header">
      <div><span className="nova-settings-eyebrow">Nova</span><h1 id={titleId}>{t('settingsTitle')}</h1></div>
      <button className="nova-settings-close nova-dismiss-button" onClick={onClose} aria-label={t('closeDialog')}>
        <NovaIcon name="close" size={20}/>
      </button>
    </header>
    <div className="nova-settings-layout">
      <nav className="nova-settings-nav" aria-label={t('settingsSections')}>
        {sectionGroups.map(group=><div key={group.id} className="nova-settings-nav-group" role="group" aria-labelledby={titleId+'-group-'+group.id}>
          <h3 id={titleId+'-group-'+group.id}>{t(group.label)}</h3>
          {group.sections.map(sectionButton)}
        </div>)}
        <div className="nova-settings-nav-footer">{sectionButton('about')}</div>
      </nav>
      <section className="nova-settings-content" aria-labelledby={['connection','embedding','projects','web','storage','knowledge'].includes(section) ? undefined : section === 'appearance' ? appearanceTitleId : sectionTitleId} aria-label={section === 'knowledge' ? t('settingsKnowledge') : section === 'storage' ? t('settingsStorage') : section === 'embedding' ? t('settingsEmbedding') : section === 'connection' ? t('settingsConnection') : section === 'projects' ? t('settingsProjects') : section === 'web' ? t('settingsWeb') : undefined}>
        {!['shortcuts', 'general', 'appearance', 'connection', 'embedding', 'projects', 'web', 'memory', 'storage','knowledge','about'].includes(section) && <div className="nova-settings-introduction"><h2 id={sectionTitleId}>{t(selected[1])}</h2><p>{t(selected[2])}</p></div>}
        {section === 'shortcuts' && <ShortcutSettings titleId={sectionTitleId} />}
        {section === 'general' && <GeneralSettings titleId={sectionTitleId} />}
        {section === 'about' ? <AboutSettings titleId={sectionTitleId} version={appVersion}>{about}</AboutSettings> : null}
        {Object.entries(slots).filter(([name]) => !locked(name)).map(([name,content]) => <div key={name} hidden={section !== name} data-settings-domain={name}>
          {content || <p className="nova-settings-empty">{t('settingsControlsUnavailable')}</p>}
        </div>)}
      </section>
    </div>
  </ModalHost>
}

function SettingsIcon({ name }: { name: SettingsSection }) {
  if (name === 'chat') return <NovaIcon name="chat" size={20} strokeWidth={1.6} />
  if (name === 'shortcuts') return <NovaIcon name="keyboard" size={20} strokeWidth={1.6} />
  if (name === 'storage') return <NovaIcon name="database" size={20} strokeWidth={1.6} />
  if (name === 'connection') return <NovaIcon name="sparkle" size={20} strokeWidth={1.6} />
  const paths: Record<Exclude<SettingsSection, 'chat' | 'shortcuts' | 'storage' | 'connection'>, ReactNode> = {
    general: <><path d="M4 7h16M4 17h16" /><circle cx="9" cy="7" r="2.5" /><circle cx="15" cy="17" r="2.5" /></>,
    appearance: <><circle cx="12" cy="12" r="9" /><path d="M12 3a9 9 0 0 0 0 18Z" fill="currentColor" stroke="none" /></>,
    embedding: <><circle cx="6" cy="6" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="12" cy="18" r="2"/><path d="m8 6 8 0M7 8l4 8m6-8-4 8"/></>,
    projects: <path d="M3 7a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v9H3Z" />,
    web: <><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3c5 5 5 13 0 18-5-5-5-13 0-18Z" /></>,
    memory: <><path d="M9 4a3 3 0 0 0-5 3 4 4 0 0 0-1 7 4 4 0 0 0 6 6m6-16a3 3 0 0 1 5 3 4 4 0 0 1 1 7 4 4 0 0 1-6 6M9 4v16m6-16v16M6 8h3m6 8h3M5 14h4m6-6h3" /></>,
    knowledge: <><path d="M4 5h6a3 3 0 0 1 2 1 3 3 0 0 1 2-1h6v15h-6a3 3 0 0 0-2 1 3 3 0 0 0-2-1H4Z" /><path d="M12 6v15" /></>,
    about: <><circle cx="12" cy="12" r="9" /><path d="M12 11v6m0-10v1" /></>,
  }
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}
