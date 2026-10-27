import { useEffect, useRef, useState } from 'react'
import { shortcutDefinitions, defaultShortcuts, bindingFromEvent, bindingIssue, type ShortcutAction } from '@nova/keyboard-shortcuts'
import { useShortcuts } from '../keyboard_shortcuts'
import { useI18n, type TranslationKey } from '../i18n'
import { NovaIcon } from './NovaIcon'

const normalize = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase().trim()
export function ShortcutSettings({ titleId }: { titleId: string }) {
  const { t } = useI18n()
  const { bindings, loaded, loadFailed, busy, state, save, label, mac } = useShortcuts()
  const [query, setQuery] = useState('')
  const [recording, setRecording] = useState<ShortcutAction | null>(null)
  const [notice, setNotice] = useState('')
  const buttons = useRef<Partial<Record<ShortcutAction, HTMLButtonElement | null>>>({})
  const groups = [['general', 'shortcutsGeneral'], ['chat', 'shortcutsChat'], ['projects', 'shortcutsProjects']] as const
  const words = normalize(query).split(/\s+/).filter(Boolean)
  const filtered = shortcutDefinitions.filter(d => {
    const text = normalize([t(d.label as TranslationKey), t(d.hint as TranslationKey), label(d.id) || t('shortcutsUnassigned')].join(' '))
    return words.every(word => text.includes(word))
  })
  useEffect(() => {
    if (!recording) return
    let active = true, ready = false
    const stop = () => { setRecording(null); setNotice('') }
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Tab') { stop(); return }
      event.preventDefault(); event.stopImmediatePropagation()
      if (event.key === 'Escape') { stop(); return }
      if (!ready || event.repeat || event.isComposing || event.keyCode === 229) return
      if (['Control', 'Meta', 'Alt', 'Shift'].includes(event.key)) return
      const remove = ['Backspace', 'Delete'].includes(event.key) && !event.ctrlKey && !event.metaKey && !event.altKey && !event.shiftKey
      const candidate = remove ? null : bindingFromEvent(event, mac)
      const issue = !remove && !candidate ? { kind: 'invalid' } : bindingIssue(recording, candidate, bindings)
      if (issue) {
        const action = shortcutDefinitions.find(d => d.id === ('action' in issue ? issue.action : null))
        setNotice(t(issue.kind === 'conflict' ? 'shortcutsConflict' : issue.kind === 'reserved' ? 'shortcutsReserved' : 'shortcutsInvalid')
          .replace('{action}', action ? t(action.label as TranslationKey) : ''))
        return
      }
      setRecording(null); setNotice(''); void save({ ...bindings, [recording]: candidate })
    }
    window.addEventListener('keydown', keydown, true)
    window.addEventListener('blur', stop)
    void window.api.setShortcutCapture(true).then(result => {
      if (active && result.success) ready = true
      else if (active) { setRecording(null); setNotice(t('shortcutsSaveFailed')) }
    }).catch(() => { if (active) { setRecording(null); setNotice(t('shortcutsSaveFailed')) } })
    buttons.current[recording]?.focus()
    return () => {
      active = false; window.removeEventListener('keydown', keydown, true); window.removeEventListener('blur', stop)
      void window.api.setShortcutCapture(false).catch(() => {})
    }
  }, [recording, bindings, mac, save, t])
  return <div className="nova-shortcuts-settings">
    <div className="nova-settings-introduction nova-shortcuts-introduction">
      <div><h2 id={titleId}>{t('settingsShortcuts')}</h2><p>{t('settingsShortcutsHint')}</p></div>
      <button className="nova-settings-reset" type="button" disabled={!loaded || busy} onClick={() => {
        setRecording(null); setNotice(''); void save(defaultShortcuts(), true)
      }}>{t('shortcutsReset')}</button>
    </div>
    <form className="nova-shortcuts-search" onSubmit={event=>{event.preventDefault();event.currentTarget.querySelector<HTMLInputElement>('input')?.focus()}}><NovaIcon name="search" size={19} />
      <input type="search" value={query} placeholder={t('shortcutsSearch')} aria-label={t('shortcutsSearch')}
        onChange={event => { setRecording(null); setNotice(''); setQuery(event.target.value) }} />
      <button type="submit" className="nova-search-submit" aria-label={t('shortcutsSearch')} title={t('shortcutsSearch')}><NovaIcon name="forward" size={18}/></button>
    </form>
    <p className="nova-shortcuts-instructions">{t('shortcutsInstructions')}</p>
    <div className="nova-shortcuts-feedback" aria-live="polite" aria-atomic="true">
      {notice ? <p className="nova-settings-error" role="alert">{notice}</p> :
        state !== 'idle' && <p className={state === 'failed' ? 'nova-settings-error' : state === 'saving' || state === 'unconfirmed' ? 'nova-settings-pending' : 'nova-settings-success'}>
          {t(state === 'failed' ? 'shortcutsSaveFailed' : state === 'saving' ? 'shortcutsSaving' : state === 'unconfirmed' ? 'settingsSaveUnconfirmed' : state === 'reset' ? 'shortcutsResetDone' : 'shortcutsSaved')}</p>}
    </div>
    {!loaded ? <p className={loadFailed ? 'nova-settings-error' : 'nova-settings-pending'} role={loadFailed ? 'alert' : 'status'}>{t(loadFailed ? 'shortcutsLoadFailed' : 'shortcutsLoading')}</p> :
      filtered.length === 0 ? <p className="nova-settings-empty" role="status">{t('shortcutsEmpty')}</p> : groups.map(([group, heading]) => {
        const rows = filtered.filter(d => d.group === group)
        return rows.length > 0 && <section key={group} className="nova-shortcut-group" aria-labelledby={`${titleId}-${group}`}>
          <h3 id={`${titleId}-${group}`}>{t(heading)}</h3>
          <div className="nova-settings-card nova-shortcut-list" aria-busy={busy}>{rows.map(d => <div key={d.id} className="nova-shortcut-row" data-shortcut={d.id}>
            <div className="nova-shortcut-copy"><span className="nova-setting-label" id={`${titleId}-${d.id}`}>{t(d.label as TranslationKey)}</span><p>{t(d.hint as TranslationKey)}</p></div>
            <div className="nova-shortcut-controls">
              <button id={`${titleId}-${d.id}-binding`} type="button" className="nova-shortcut-binding" data-recording={recording === d.id || undefined}
                ref={element => { buttons.current[d.id] = element }} disabled={busy} aria-labelledby={`${titleId}-${d.id} ${titleId}-${d.id}-binding`}
                onBlur={() => { if (recording === d.id) { setRecording(null); setNotice('') } }}
                onClick={() => { setNotice(''); setRecording(current => current === d.id ? null : d.id) }}>
                {recording === d.id ? t('shortcutsCapture') : bindings[d.id] ? <kbd>{label(d.id)}</kbd> : <span className="nova-shortcut-unassigned">{t('shortcutsUnassigned')}</span>}
              </button>
              {bindings[d.id] && <button className="nova-shortcut-remove nova-dismiss-button" type="button" disabled={busy} aria-label={`${t('shortcutsRemove')}: ${t(d.label as TranslationKey)}`}
                title={t('shortcutsRemove')} onClick={() => { setRecording(null); setNotice(''); void save({ ...bindings, [d.id]: null }) }}><NovaIcon name="close" size={14} /></button>}
            </div>
          </div>)}</div>
        </section>
      })}
  </div>
}
