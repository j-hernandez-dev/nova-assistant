import { useEffect, useId, useRef, useState, type CSSProperties } from 'react'
import type { DesktopSessionView } from '../../shared/application'
import { useI18n } from '../i18n'
import { useSettingsAction } from '../settings_actions'

export const CONTEXT_PRESETS = [4096, 8192, 16384, 32768, 65536] as const
const label = (tokens: number) => `${tokens / 1024}K`

/** Draft only. Application validates, persists and reports the actual selection. */
export function ContextSettings({ view }: { view: DesktopSessionView | null }) {
  const { t } = useI18n()
  const context = view?.context
  const requested = context?.requestedTokens
  const [draft, setDraft] = useState(requested ?? 0)
  const previous = useRef(requested)
  const submitted = useRef<number | null>(null)
  const id = useId()
  const action = useSettingsAction(`context:${view?.sessionId}:${view?.status.ready}:${draft}`)
  useEffect(() => {
    const old = previous.current
    setDraft(value => value === old || old === undefined ? requested ?? 0 : value)
    previous.current = requested
  }, [requested])
  const unavailable = !context || !view?.status.ready || view.recovering
  const running = !!view?.activeTurnId || !!view?.activeGenerationId || !!view?.approvals.length || !!view?.inputs.length
  const disabled = unavailable || running || action.busy
  const selected = draft || context?.selectedTokens || 8192
  const index = Math.max(0, CONTEXT_PRESETS.indexOf(selected as typeof CONTEXT_PRESETS[number]))
  const error = action.errorCode || context?.errorCode
  const errorKey = error === 'CONTEXT_LIMIT_EXCEEDED' || error === 'CONTEXT_UNSUPPORTED' ? 'contextLimitError'
    : error === 'CONTEXT_PREFERENCES_SAVE_FAILED' ? 'contextSaveError'
    : error === 'CONFLICT_ACTIVE_OPERATION' || error === 'PROJECT_BUSY' ? 'contextBusy'
    : error === 'REVISION_CONFLICT' ? 'contextRevisionError' : 'contextOperationError'
  const confirmed = !!action.result && requested === draft
  return <form className="nova-settings-card nova-context-settings" aria-busy={action.busy}
    onSubmit={event => {
      event.preventDefault()
      if (!disabled && draft !== requested) {
        submitted.current = draft
        void action.run(() => window.api.applicationCommand('SetContextWindow', { requestedTokens: draft }))
      }
    }}>
    <div className="nova-context-heading">
      <label htmlFor={id}>{t('contextTokens')}</label>
      <output htmlFor={id}>{draft === 0 ? t('contextAuto') : label(draft)}</output>
    </div>
    <p className="settings-hint" id={`${id}-hint`}>{t('contextTokensHint')}</p>
    <label className="settings-toggle-row" htmlFor={`${id}-auto`}>
      <input id={`${id}-auto`} type="checkbox" checked={draft === 0} disabled={disabled}
        onChange={event => setDraft(event.target.checked ? 0 : CONTEXT_PRESETS[index])} />
      {t('contextAutomatic')}
    </label>
    <input id={id} className="nova-context-slider" type="range" min="0" max="4" step="1" value={index}
      disabled={disabled || draft === 0} aria-describedby={`${id}-hint`} aria-valuetext={label(CONTEXT_PRESETS[index])}
      style={{ '--context-fill': `${index * 25}%` } as CSSProperties}
      onChange={event => setDraft(CONTEXT_PRESETS[Number(event.target.value)])} />
    <div className="nova-context-ticks" aria-label={t('contextPresets')}>
      {CONTEXT_PRESETS.map(tokens => <button key={tokens} type="button" disabled={disabled}
        aria-pressed={draft === tokens} onClick={() => setDraft(tokens)}>{label(tokens)}</button>)}
    </div>
    {context?.selectedTokens && <p className="settings-hint">{t('contextSelected')}: <strong>{label(context.selectedTokens)}</strong></p>}
    {unavailable && <p className="settings-hint" role="status">{t('settingsControlsUnavailable')}</p>}
    {running && <p className="settings-hint" role="status">{t('contextBusy')}</p>}
    {error && <p className="nova-settings-error" role="alert">{t(errorKey)}</p>}
    {action.unconfirmed && <p className="nova-settings-error" role="status">{t('settingsSaveUnconfirmed')}</p>}
    {action.result && submitted.current === draft && <p className="nova-settings-success" role="status">{t(confirmed ? 'contextSaved' : 'contextApplying')}</p>}
    <div className="nova-settings-actions">
      <button type="button" className="nova-settings-secondary" disabled={disabled || draft === requested}
        onClick={() => setDraft(requested ?? 0)}>{t('settingsCancel')}</button>
      <button type="submit" className="nova-settings-primary" disabled={disabled || draft === requested}>
        {t(action.busy ? 'settingsSaving' : 'settingsSave')}
      </button>
    </div>
  </form>
}
