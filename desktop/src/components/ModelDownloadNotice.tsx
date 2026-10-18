import type { ModelDownloadState } from '../../shared/application'
import { useI18n } from '../i18n'

export function ModelDownloadNotice({ download, onRetry }: { download: ModelDownloadState | null; onRetry: () => void }) {
  const { t } = useI18n()
  if (!download || download.phase === 'complete') return null
  const { phase, model, percent, detail } = download
  const refreshing = phase === 'refreshing' || phase === 'refresh-failed'
  const message = phase === 'failed' ? 'modelDownloadFailureHint' : phase === 'waiting' ? 'modelDownloadWaiting'
    : phase === 'refresh-failed' ? 'modelDownloadRefreshFailed' : refreshing ? 'modelDownloadRefreshing' : 'modelDownloadLockHint'
  return <section className="nova-readiness-notice nova-download-notice" aria-label={t('modelDownloadTitle')} data-phase={phase}>
    <div className="nova-download-heading" role="status" aria-live="polite">
      <strong>{t(refreshing ? 'modelDownloadUpdating' : phase === 'failed' ? 'modelDownloadFailedTitle' : 'modelDownloadTitle')} <span>{model}</span></strong>
      {percent !== null && phase !== 'failed' && <span className="nova-download-percent">{percent}%</span>}
    </div>
    {phase !== 'failed' && <div className="nova-download-track" role="progressbar" aria-label={model}
      aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent ?? undefined} data-indeterminate={percent === null || undefined}>
      <div style={{ width: percent === null ? '35%' : percent + '%' }} />
    </div>}
    <p className="nova-download-detail">{detail || t(message)}</p>
    {detail && <p className="nova-download-hint">{t(message)}</p>}
    {phase === 'refresh-failed' && <div className="nova-readiness-actions"><button type="button" onClick={onRetry}>{t('modelDownloadRetryInventory')}</button></div>}
  </section>
}
