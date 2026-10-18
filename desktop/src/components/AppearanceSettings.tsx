import { useEffect, useId, useRef, useState } from 'react'
import { useI18n } from '../i18n'
import { applyAppearance, defaultAppearance, readAppearance, type AppearancePreferences } from '../../shared/desktop_appearance'

/** Saved presentation only. A failed save never changes the effective motion preference. */
export function AppearanceSettings() {
  const { t } = useI18n()
  const id = useId()
  const [saved, setSaved] = useState<AppearancePreferences>(defaultAppearance)
  const [draft, setDraft] = useState<AppearancePreferences>(defaultAppearance)
  const [load, setLoad] = useState<'loading' | 'ready' | 'failed'>('loading')
  const [state, setState] = useState<'idle' | 'saving' | 'unconfirmed' | 'saved' | 'failed'>('idle')
  const alive = useRef(true), saving = useRef(false)
  const busy = state === 'saving' || state === 'unconfirmed'
  const changed = draft.reduceMotion !== saved.reduceMotion || draft.showStartupScreen !== saved.showStartupScreen
  useEffect(() => {
    alive.current = true
    let current = true
    const timer = setTimeout(() => { if (current) { current = false; setLoad('failed') } }, 15000)
    const api = typeof window === 'undefined' ? undefined : window.api
    if (typeof api?.getDesktopPreferences !== 'function') { clearTimeout(timer); setLoad('failed') }
    else void api.getDesktopPreferences().then(value => {
      if (!current || !alive.current) return
      if (value.schemaVersion !== 1) { setLoad('failed'); return }
      const preferences = readAppearance(value)
      setSaved(preferences); setDraft(preferences); applyAppearance(document, preferences); setLoad('ready')
    }).catch(() => { if (current && alive.current) setLoad('failed') }).finally(() => clearTimeout(timer))
    return () => { current = false; alive.current = false; clearTimeout(timer) }
  }, [])
  async function save() {
    if (saving.current || load !== 'ready' || !changed) return
    saving.current = true; setState('saving')
    const next = { ...draft }
    const timer = setTimeout(() => { if (alive.current) setState('unconfirmed') }, 15000)
    try {
      const result = await window.api.setDesktopAppearance(next)
      const accepted = result.success && result.preferences.reduceMotion === next.reduceMotion &&
        result.preferences.showStartupScreen === next.showStartupScreen
      if (accepted) applyAppearance(document, next)
      if (alive.current) {
        setState(accepted ? 'saved' : 'failed')
        if (accepted) { setSaved(next); setDraft(next) }
      }
    } catch { if (alive.current) setState('failed') }
    finally { saving.current = false; clearTimeout(timer) }
  }
  if (load !== 'ready') return <p className={load === 'failed' ? 'nova-settings-error' : 'nova-settings-pending'}
    role={load === 'failed' ? 'alert' : 'status'}>{t(load === 'failed' ? 'appearanceLoadFailed' : 'appearanceLoading')}</p>
  return <form className="nova-settings-card nova-appearance-settings" aria-busy={busy}
    onSubmit={event => { event.preventDefault(); void save() }}>
    <div className="nova-settings-row nova-appearance-row">
      <div><label htmlFor={id + '-motion'}>{t('appearanceReduceMotion')}</label><p id={id + '-motion-hint'}>{t('appearanceMotionHint')}</p></div>
      <input id={id + '-motion'} data-appearance="reduceMotion" type="checkbox" role="switch" checked={draft.reduceMotion}
        aria-describedby={id + '-motion-hint'} disabled={busy} onChange={event => {
          setDraft(value => ({ ...value, reduceMotion: event.target.checked })); setState('idle')
        }} />
    </div>
    <div className="nova-settings-row nova-appearance-row">
      <div><label htmlFor={id + '-startup'}>{t('appearanceStartupScreen')}</label><p id={id + '-startup-hint'}>{t('appearanceStartupHint')}</p></div>
      <input id={id + '-startup'} data-appearance="showStartupScreen" type="checkbox" role="switch" checked={draft.showStartupScreen}
        aria-describedby={id + '-startup-hint'} disabled={busy} onChange={event => {
          setDraft(value => ({ ...value, showStartupScreen: event.target.checked })); setState('idle')
        }} />
    </div>
    <p className="nova-settings-apply-note">{t('appearanceApplyHint')}</p>
    {state === 'saved' && <p className="nova-settings-success" role="status">{t('settingsSaved')}</p>}
    {state === 'failed' && <p className="nova-settings-error" role="alert">{t('appearanceSaveFailed')}</p>}
    {state === 'unconfirmed' && <p className="nova-settings-error" role="status">{t('settingsSaveUnconfirmed')}</p>}
    <div className="nova-settings-actions">
      <button type="button" className="nova-settings-secondary" disabled={busy || !changed}
        onClick={() => { setDraft(saved); setState('idle') }}>{t('settingsCancel')}</button>
      <button type="submit" className="nova-settings-primary" disabled={busy || !changed}>
        {t(state === 'saving' ? 'settingsSaving' : 'settingsSave')}
      </button>
    </div>
  </form>
}
