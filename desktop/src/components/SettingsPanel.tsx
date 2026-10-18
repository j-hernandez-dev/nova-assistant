import { useState, useEffect, useRef, useId, type ReactNode } from 'react'
import { ModalHost } from './ModalHost'
import { AppearanceSettings } from './AppearanceSettings'
import { useI18n, type DesktopLocale } from '../i18n'
import '../settings.css'

export type SettingsSection = 'general' | 'appearance' | 'chat' | 'connection' | 'projects' | 'web' | 'memory' | 'knowledge' | 'about'

type Props = {
  open?: boolean
  backendLocked?: boolean
  onClose: () => void
  initialSection?: SettingsSection
  chat?: ReactNode
  connection?: ReactNode
  projects?: ReactNode
  web?: ReactNode
  memory?: ReactNode
  knowledge?: ReactNode
  about?: ReactNode
}

const sections = [
  ['general', 'settingsGeneral', 'settingsGeneralHint'],
  ['appearance', 'settingsAppearance', 'settingsAppearanceHint'],
  ['connection', 'settingsConnection', 'settingsConnectionHint'],
  ['projects', 'settingsProjects', 'settingsProjectsHint'],
  ['chat', 'settingsChat', 'settingsChatHint'],
  ['web', 'settingsWeb', 'settingsWebHint'],
  ['memory', 'settingsMemory', 'settingsMemoryHint'],
  ['knowledge', 'settingsKnowledge', 'settingsKnowledgeHint'],
  ['about', 'settingsAbout', 'settingsAboutHint'],
] as const

/** A timeout reports uncertainty; only the persistence receipt can confirm the save. */
export async function persistLocaleDraft(persist: (next: DesktopLocale) => Promise<boolean>, next: DesktopLocale,
  onUnconfirmed: () => void, delay = 15000): Promise<boolean> {
  const timer = setTimeout(onUnconfirmed, delay)
  try { return await persist(next) } catch { return false } finally { clearTimeout(timer) }
}

export function SettingsPanel({ onClose, open = true, initialSection = 'general', backendLocked = false, chat, connection, projects, web, memory, knowledge, about }: Props) {
  const { t, locale, setLocale } = useI18n()
  const [section, setSection] = useState<SettingsSection>(initialSection)
  const [draftLocale, setDraftLocale] = useState<DesktopLocale>(locale)
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'unconfirmed' | 'saved' | 'failed'>('idle')
  const [appVersion, setAppVersion] = useState<string | null>(null)
  const previousLocale = useRef(locale)
  const saving = useRef(false)
  const alive = useRef(true)
  const titleId = useId()
  const sectionTitleId = useId()
  const busy = saveState === 'saving' || saveState === 'unconfirmed'
  const locked = (name: string) => backendLocked && !['general', 'appearance', 'about'].includes(name)
  useEffect(() => { if (backendLocked) setSection(current => ['general', 'appearance', 'about'].includes(current) ? current : 'general') }, [backendLocked])

  useEffect(() => {
    alive.current = true
    return () => { alive.current = false }
  }, [])

  useEffect(() => {
    setDraftLocale(draft => draft === previousLocale.current ? locale : draft)
    previousLocale.current = locale
  }, [locale])

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

  const saveLocale = async () => {
    if (saving.current || draftLocale === locale) return
    saving.current = true
    setSaveState('saving')
    const next = draftLocale
    const success = await persistLocaleDraft(setLocale, next, () => {
      if (alive.current) setSaveState('unconfirmed')
    })
    saving.current = false
    if (!alive.current) return
    setSaveState(success ? 'saved' : 'failed')
    if (success) setDraftLocale(next)
  }

  const slots = { appearance: <AppearanceSettings />, chat, connection, projects, web, memory, knowledge }
  const selected = sections.find(([id]) => id === section) || sections[0]

  return <ModalHost open={open} onClose={onClose} labelledBy={titleId} className="nova-settings-dialog">
    <header className="nova-settings-header">
      <div><span className="nova-settings-eyebrow">Nova</span><h1 id={titleId}>{t('settingsTitle')}</h1></div>
      <button className="nova-settings-close" onClick={onClose} aria-label={t('closeDialog')}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg>
      </button>
    </header>
    <div className="nova-settings-layout">
      <nav className="nova-settings-nav" aria-label={t('settingsSections')}>
        {sections.map(([id, label]) => <button key={id} type="button" data-settings-section={id} aria-current={section === id ? 'page' : undefined}
          disabled={locked(id)} title={locked(id) ? t('modelDownloadBusy') : undefined}
          onClick={() => setSection(id)}><SettingsIcon name={id} /><span>{t(label)}</span></button>)}
      </nav>
      <section className="nova-settings-content" aria-labelledby={sectionTitleId}>
        <div className="nova-settings-introduction"><h2 id={sectionTitleId}>{t(selected[1])}</h2><p>{t(selected[2])}</p></div>
        {section === 'general' ? <>
          <GeneralSettingsForm locale={locale} draftLocale={draftLocale} saveState={saveState} onChange={next => {
            setDraftLocale(next); setSaveState('idle')
          }} onSave={() => void saveLocale()} onCancel={() => { setDraftLocale(locale); setSaveState('idle') }} />
          <div className="nova-settings-card nova-settings-shortcuts">
            <h3>{t('keyboardShortcuts')}</h3>
            <div><span>{t('settings')}</span><kbd>Ctrl/Cmd+,</kbd></div>
            <div><span>{t('toggleExplorer')}</span><kbd>Ctrl/Cmd+B</kbd></div>
            <div><span>{t('stopHint')}</span><kbd>Esc</kbd></div>
            <div><span>{t('newLine')}</span><kbd>Shift+Enter</kbd></div>
          </div>
        </> : section === 'about' ? <>
          <div className="nova-settings-card nova-settings-version">
            <span>{t('settingsDesktopVersion')}</span>
            <strong>{appVersion === null ? t('checking') : appVersion ? `v${appVersion}` : t('settingsVersionUnavailable')}</strong>
          </div>
          {about}
        </> : null}
        {Object.entries(slots).filter(([name]) => !locked(name)).map(([name,content]) => <div key={name} hidden={section !== name} data-settings-domain={name}>
          {content || <p className="nova-settings-empty">{t('settingsControlsUnavailable')}</p>}
        </div>)}
        {busy && section !== 'general' && <p className="nova-settings-pending" role="status">{t(saveState === 'unconfirmed' ? 'settingsSaveUnconfirmed' : 'settingsSaving')}</p>}
      </section>
    </div>
  </ModalHost>
}

type GeneralProps = {
  locale: DesktopLocale
  draftLocale: DesktopLocale
  saveState: 'idle' | 'saving' | 'unconfirmed' | 'saved' | 'failed'
  onChange: (locale: DesktopLocale) => void
  onSave: () => void
  onCancel: () => void
}

export function GeneralSettingsForm({ locale, draftLocale, saveState, onChange, onSave, onCancel }: GeneralProps) {
  const { t } = useI18n()
  const id = useId()
  const busy = saveState === 'saving' || saveState === 'unconfirmed'
  return <form className="nova-settings-card" onSubmit={event => { event.preventDefault(); onSave() }} aria-busy={busy}>
    <div className="nova-settings-row">
      <div><label htmlFor={id}>{t('language')}</label><p id={`${id}-hint`}>{t('settingsLanguageHint')}</p></div>
      <select id={id} value={draftLocale} disabled={busy} aria-describedby={`${id}-hint`}
        onChange={event => onChange(event.target.value as DesktopLocale)}>
        <option value="es">Español</option><option value="en">English</option>
      </select>
    </div>
    <p className="nova-settings-apply-note">{t('settingsApplyOnSave')}</p>
    {saveState === 'saved' && <p className="nova-settings-success" role="status">{t('settingsSaved')}</p>}
    {saveState === 'failed' && <p className="nova-settings-error" role="alert">{t('localeSaveFailed')}</p>}
    {saveState === 'unconfirmed' && <p className="nova-settings-error" role="status">{t('settingsSaveUnconfirmed')}</p>}
    <div className="nova-settings-actions">
      <button type="button" className="nova-settings-secondary" onClick={onCancel} disabled={busy || draftLocale === locale}>{t('settingsCancel')}</button>
      <button type="submit" className="nova-settings-primary" disabled={busy || draftLocale === locale}>
        {saveState === 'saving' ? t('settingsSaving') : t('settingsSave')}
      </button>
    </div>
  </form>
}

function SettingsIcon({ name }: { name: SettingsSection }) {
  const paths: Record<SettingsSection, ReactNode> = {
    general: <><path d="M4 7h16M4 17h16" /><circle cx="9" cy="7" r="2.5" /><circle cx="15" cy="17" r="2.5" /></>,
    appearance: <><circle cx="12" cy="12" r="9" /><path d="M12 3a9 9 0 0 0 0 18Z" fill="currentColor" stroke="none" /></>,
    chat: <path d="M5 4h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H9l-6 3V6a2 2 0 0 1 2-2Z" />,
    connection: <><rect x="4" y="4" width="16" height="11" rx="2" /><path d="M8 20h8M12 15v5m-4-10 2-2 2 2 3-3" /></>,
    projects: <path d="M3 7a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v9H3Z" />,
    web: <><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3c5 5 5 13 0 18-5-5-5-13 0-18Z" /></>,
    memory: <><path d="M9 4a3 3 0 0 0-5 3 4 4 0 0 0-1 7 4 4 0 0 0 6 6m6-16a3 3 0 0 1 5 3 4 4 0 0 1 1 7 4 4 0 0 1-6 6M9 4v16m6-16v16M6 8h3m6 8h3M5 14h4m6-6h3" /></>,
    knowledge: <><path d="M4 5h6a3 3 0 0 1 2 1 3 3 0 0 1 2-1h6v15h-6a3 3 0 0 0-2 1 3 3 0 0 0-2-1H4Z" /><path d="M12 6v15" /></>,
    about: <><circle cx="12" cy="12" r="9" /><path d="M12 11v6m0-10v1" /></>,
  }
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}
