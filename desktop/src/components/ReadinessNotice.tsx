import { useRef, useState, type ReactNode } from 'react'
import { useI18n, type TranslationKey } from '../i18n'

const REASON_MESSAGES: Record<string, TranslationKey> = {
  CHECKING: 'readinessChecking',
  BACKEND_DISCONNECTED: 'readinessBackendDisconnected',
  INVALID_SESSION: 'readinessBackendDisconnected',
  OLLAMA_UNAVAILABLE: 'readinessOllamaUnavailable',
  OLLAMA_CONNECTION_TIMEOUT: 'modelConnectTimeout',
  NO_MODELS_INSTALLED: 'readinessNoModels',
  MODEL_NOT_SELECTED: 'readinessSelectModel',
  MODEL_NOT_INSTALLED: 'readinessModelMissing',
  MODEL_NOT_CHAT_CAPABLE: 'readinessModelNotChat',
  MODEL_TOOL_SUPPORT_UNAVAILABLE: 'readinessModelNoTools',
  MODEL_VALIDATION_FAILED: 'readinessModelValidation',
  PROVIDER_UNVERIFIED: 'readinessProviderUnverified',
  READINESS_STALE: 'readinessStale',
  READINESS_CHECK_FAILED: 'readinessCheckFailed',
}

type Props = {
  ready: boolean
  reason: string | null
  requiredAction: 'SELECT_MODEL' | 'CONFIGURE_PROVIDER' | null
  modelChanging?: boolean
  responseDelayed?: boolean
  onConfigure: () => void
  onRecheck: () => Promise<void>
  configuration?: ReactNode
}

/** Readiness is a host projection. This card only explains the reported state. */
export function ReadinessNotice({ ready, reason, requiredAction, modelChanging = false,
  onConfigure, onRecheck, configuration, responseDelayed = false }: Props) {
  const { t } = useI18n()
  const inFlight = useRef(false)
  const [checking, setChecking] = useState(false)
  const [checkFailed, setCheckFailed] = useState(false)
  if (ready && !modelChanging && !responseDelayed) return null
  const isChecking = checking || reason === 'CHECKING' || modelChanging
  const canConfigure = !modelChanging && requiredAction !== null && reason !== 'OLLAMA_UNAVAILABLE'
  const title = responseDelayed ? 'modelResponseDelayedTitle' : canConfigure ? 'finishSetup' : isChecking ? 'readinessCheckingTitle' : 'readinessStatusTitle'
  const message = responseDelayed && !checkFailed ? 'modelResponseTimeout' : modelChanging ? 'modelChanging' : checkFailed
    ? 'readinessCheckFailed' : REASON_MESSAGES[reason || 'READINESS_CHECK_FAILED'] || 'readinessCheckFailed'

  async function recheck() {
    if (isChecking || inFlight.current) return
    inFlight.current = true
    setChecking(true)
    setCheckFailed(false)
    try { await onRecheck() }
    catch { setCheckFailed(true) }
    finally { inFlight.current = false; setChecking(false) }
  }

  return <section className="nova-readiness-notice" aria-label={t(title)}>
    <div className="nova-readiness-copy" role="status" aria-live="polite">
      <strong>{t(title)}</strong>
      <p>{t(message)}</p>
    </div>
    <div className="nova-readiness-actions">
      {canConfigure && <button type="button" disabled={modelChanging} onClick={onConfigure}>{t('openConfiguration')}</button>}
      <button type="button" disabled={isChecking} onClick={() => void recheck()}>
        {isChecking ? t('checking') : t(reason === 'BACKEND_DISCONNECTED' ? 'restartBackend' : 'recheckReadiness')}
      </button>
    </div>
    {configuration && <div className="nova-readiness-configuration">{configuration}</div>}
  </section>
}
