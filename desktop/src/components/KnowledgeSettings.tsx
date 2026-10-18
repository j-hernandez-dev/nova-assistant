import { useEffect, useRef, useState } from 'react'
import type { DesktopSessionView, CommandReceipt } from '../../shared/application'
import { useI18n } from '../i18n'
import { useSettingsAction, SettingsActionFeedback } from '../settings_actions'
import { settingStateKey, settingErrorKey } from '../settings_services_locale'

type Props = {
  view: DesktopSessionView | null
  selectedSources: string[]
  onSelectedSources: (ids: string[]) => void
}

/** Existing Knowledge and RAG controls. All acquisition, consent and effects stay in the host. */
export function KnowledgeSettings({ view, selectedSources, onSelectedSources }: Props) {
  const { t } = useI18n()
  const scope = `${view?.sessionId || ''}:${view?.workspace || ''}`
  const action = useSettingsAction(scope)
  const ragAction = useSettingsAction(scope)
  const cancelAction = useSettingsAction(scope)
  const [sourceUrl, setSourceUrl] = useState('')
  const [ragQuery, setRagQuery] = useState('')
  const [ragEnabled, setRagEnabled] = useState(view?.rag.enabled || false)
  const [ragSubmitted,setRagSubmitted]=useState<boolean|null>(null)
  const selectedRef = useRef(selectedSources)
  selectedRef.current = selectedSources
  const previousRagEnabled = useRef(view?.rag.enabled || false)
  const knowledge = view?.knowledge
  const ready = !!view?.status.ready && !view.recovering && !view.gap
  const streaming = !!view?.activeTurnId
  const closing = !!knowledge?.closing
  const busy = action.busy || cancelAction.busy
  const mutationDisabled = !ready || streaming || closing || busy
  const attachments = knowledge?.attachmentRefs || []
  const operations = view?.knowledgeOperations || []
  const rag = view?.rag
  const ragWaiting=!!ragAction.result?.accepted&&ragSubmitted!==null&&rag?.enabled!==ragSubmitted

  useEffect(() => {
    const effective = view?.rag.enabled || false
    setRagEnabled(draft => draft === previousRagEnabled.current ? effective : draft)
    previousRagEnabled.current = effective
  }, [view?.rag.enabled])
  useEffect(() => { setRagEnabled(view?.rag.enabled || false); setRagQuery(''); setSourceUrl('') }, [scope])

  const command = (name: string, args: Record<string, unknown>) => {
    void action.run(() => window.api.knowledgeCommand(name, args))
  }
  const deleteSource = async (sourceId: string) => {
    const receipt = await action.run(() => window.api.knowledgeCommand('source_delete', { sourceId }))
    // The receipt confirms acceptance, not completion. Host snapshots report the real operation outcome.
    if (receipt?.accepted) onSelectedSources(selectedRef.current.filter(id => id !== sourceId))
  }
  const selectSource = (sourceId: string, checked: boolean) => {
    const next = checked ? [...new Set([...selectedSources, sourceId])] : selectedSources.filter(id => id !== sourceId)
    onSelectedSources(next)
  }
  const run = (request: () => Promise<CommandReceipt>) => { void action.run(request) }

  return <>
    <section className="settings-section" aria-label={t('sources')}>
      <h3 className="settings-section-title">{t('sources')}</h3>
      <p className="settings-hint">{t('settingsSourceHint')}</p>
      {!knowledge?.hostAcquisition ? <p role="status">{t('settingsSourceUnavailable')}</p> : <>
        <div className="settings-control-actions">
          <button className="settings-check-btn" disabled={mutationDisabled} onClick={() => run(() => window.api.knowledgePick())}>{t('attach')}</button>
          <button className="settings-check-btn" disabled={!ready || closing || busy} onClick={() => command('source_list', {})}>{t('listSources')}</button>
          <button className="settings-check-btn" disabled={!ready || closing || busy} onClick={() => command('source_status', {})}>{t('capacityStatus')}</button>
        </div>
        <form className="settings-control-form" onSubmit={event => { event.preventDefault(); if (!mutationDisabled && sourceUrl.trim()) command('source_import_url', { url: sourceUrl.trim(), scope: 'WORKSPACE' }) }}>
          <label htmlFor="nova-settings-source-url">{t('sourceUrl')}</label>
          <input id="nova-settings-source-url" value={sourceUrl} disabled={busy} onChange={event => setSourceUrl(event.target.value)} placeholder={t('publicSnapshot')} />
          <button className="settings-check-btn" disabled={mutationDisabled || !sourceUrl.trim()}>{t('importUrl')}</button>
        </form>
        <SettingsActionFeedback action={action} />
        {knowledge.capacity?.usage.map(usage => <div className="settings-capacity" key={usage.scope}>
          <div><span>{t(usage.scope === 'WORKSPACE' ? 'settingsScopeWorkspace' : usage.scope === 'SESSION' ? 'knowledgeScopeSession' : 'knowledgeScopeOther')}</span>
            <span>{t(settingStateKey(usage.state))}</span></div>
          <p>{usage.bytes} / {usage.byteLimit} bytes · {usage.sources} {t('sources')}</p>
          <details><summary>{t('diagnosticDetails')}</summary><code>{usage.scope}: {usage.state}</code></details>
        </div>)}
        {!knowledge.extraction && <p className="settings-hint">{t('extractionUnavailable')}</p>}
        <h4 className="settings-section-title">{t('settingsSelectedSources')} ({selectedSources.length})</h4>
        {attachments.length === 0 && <p className="settings-hint">{t('knowledgeNoAttachments')}</p>}
        {attachments.map(ref => <article className="settings-source-card" key={ref.attachmentId}>
          <label className="settings-toggle-row"><input type="checkbox" checked={selectedSources.includes(ref.sourceId)}
            disabled={busy || closing} onChange={event => selectSource(ref.sourceId, event.target.checked)} />
            <span>{ref.displayName}</span></label>
          <p className="settings-hint">{t(settingStateKey(ref.state))}</p>
          <div className="settings-control-actions">
            <button className="settings-check-btn" disabled={mutationDisabled} onClick={() => command('source_promote', { sourceId: ref.sourceId })}>{t('keepWorkspace')}</button>
            <button className="settings-check-btn" disabled={!ready || closing || busy} onClick={() => command('source_detail', { sourceId: ref.sourceId })}>{t('detail')}</button>
            <button className="settings-check-btn" disabled={mutationDisabled} onClick={() => run(() => window.api.knowledgeRefresh(ref.sourceId))}>{t('refreshFile')}</button>
            <button className="settings-check-btn" disabled={mutationDisabled || !sourceUrl.trim()} onClick={() => command('source_refresh_url', { sourceId: ref.sourceId, url: sourceUrl.trim() })}>{t('refreshUrl')}</button>
            <button className="settings-check-btn" disabled={mutationDisabled} onClick={() => run(() => window.api.knowledgeExport(ref.sourceId))}>{t('exportSource')}</button>
            <button className="settings-check-btn" disabled={mutationDisabled} onClick={() => command('source_remote', { sourceId: ref.sourceId, allowed: true })}>{t('settingsSourceRemote')}</button>
            <button className="settings-check-btn" disabled={mutationDisabled} onClick={() => command('source_remote', { sourceId: ref.sourceId, allowed: false })}>{t('settingsSourceLocal')}</button>
            <button className="settings-check-btn" disabled={mutationDisabled} onClick={() => void deleteSource(ref.sourceId)}>{t('deleteSource')}</button>
          </div>
          <details><summary>{t('diagnosticDetails')}</summary><code>{ref.state} · {ref.sourceId} · {ref.revisionId || t('settingsUnknown')}</code></details>
        </article>)}
      </>}
    </section>
    {operations.length > 0 && <section className="settings-section" aria-label={t('knowledgeOperations')}>
      <h3 className="settings-section-title">{t('knowledgeOperations')}</h3>
      {operations.map(operation => <article className="settings-source-operation" key={operation.operationId}>
        <p role="status">{t(settingStateKey(operation.status))}</p>
        {operation.result?.error && <p role="alert">{t(settingErrorKey(operation.result.error.code))}</p>}
        <details><summary>{t('diagnosticDetails')}</summary><code>{operation.phase} · {operation.status} · {operation.operationId}
          {operation.result?.error?.code ? ` · ${operation.result.error.code}` : ''}</code>
          {operation.result?.data && <pre>{JSON.stringify(operation.result.data, null, 2)}</pre>}
        </details>
        {operation.status === 'running' && <button className="settings-check-btn" disabled={!ready || cancelAction.busy}
          onClick={() => void cancelAction.run(() => window.api.knowledgeCommand('source_cancel', { operationId: operation.operationId }))}>{t('cancelImport')}</button>}
      </article>)}
      <SettingsActionFeedback action={cancelAction} />
    </section>}
    <section className="settings-section" data-testid="rag-panel">
      <h3 className="settings-section-title">{t('projectRetrieval')}</h3>
      <p className="settings-hint">{t('settingsRagHint')} {t('settingsSessionOnly')}</p>
      <label className="settings-toggle-row"><input type="checkbox" checked={ragEnabled}
        disabled={!rag || !ready || streaming || ragAction.busy || ragWaiting || !!view?.ragProgress} onChange={event => setRagEnabled(event.target.checked)} />{t('enableProjectRetrieval')}</label>
      <div className="settings-control-actions">
        <button className="settings-check-btn" disabled={!rag || !ready || streaming || ragAction.busy || ragWaiting || !!view?.ragProgress || ragEnabled === rag.enabled}
          onClick={() => { if(ragAction.busy||ragWaiting)return;setRagSubmitted(ragEnabled);void ragAction.run(() => window.api.applicationCommand('SetRAGEnabled', { enabled: ragEnabled })) }}>{t('settingsRagStart')}</button>
        <button className="settings-check-btn" disabled={!rag || ragAction.busy || ragWaiting || ragEnabled === rag.enabled}
          onClick={() => setRagEnabled(rag?.enabled || false)}>{t('settingsServiceCancel')}</button>
      </div>
      <p role="status">{t('settingsEffective')}: {t(rag ? rag.enabled ? 'settingsOn' : 'settingsOff' : 'settingsUnknown')} · {t(settingStateKey(rag?.availability))}</p>
      {view?.ragProgress && <p role="status">{t('knowledgeIndexing')}</p>}
      {rag?.error && <p role="alert">{t('settingsRagUnavailable')}</p>}
      <SettingsActionFeedback action={ragAction} />
      <form className="settings-control-form" onSubmit={event => { event.preventDefault(); if (rag?.enabled && ragQuery.trim() && !ragAction.busy && ready && !streaming && !view?.ragProgress) void ragAction.run(() => window.api.applicationCommand('QueryRAG', { query: ragQuery.trim() })) }}>
        <label htmlFor="nova-settings-rag-query">{t('projectQuery')}</label>
        <input id="nova-settings-rag-query" value={ragQuery} onChange={event => setRagQuery(event.target.value)} disabled={ragAction.busy} />
        <button className="settings-check-btn" disabled={!rag?.enabled || !ready || streaming || !!view?.ragProgress || ragAction.busy || !ragQuery.trim()}>{t('queryProject')}</button>
      </form>
      {view?.ragResult?.matches?.map((match, index) => <article className="settings-source-card" key={index}>
        <strong>{typeof match.file_path === 'string' ? match.file_path : ''}</strong>
        <p>{typeof match.content === 'string' ? match.content : ''}</p>
      </article>)}
      <details><summary>{t('diagnosticDetails')}</summary><code>{rag?.availability || 'UNKNOWN'}{rag?.error?.code ? ` · ${rag.error.code}` : ''}</code>
        {view?.ragProgress && <pre>{view.ragProgress}</pre>}
      </details>
    </section>
  </>
}
