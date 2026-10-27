import type {KnowledgeCitations, SourceContext as SourceContextEntry} from '../../shared/application'
import {useI18n} from '../i18n'
import {sourceReferenceIcon, sourceReferenceLocation} from '../source_reference'
import {NovaIcon} from './NovaIcon'

export function SourceContext({sources}: {sources?: SourceContextEntry[]}) {
  const {t, general} = useI18n()
  if (!sources?.length) return null
  const list = <ul className="nova-source-context-list">{sources.map(source => <li key={source.sourceId} data-source-context={source.status}>
    <strong>{source.displayName}</strong><span>{t(source.status === 'complete' ? 'sourceContextComplete'
      : source.status === 'partial' ? 'sourceContextPartial' : 'sourceContextUnavailable')}</span>
    {source.status === 'partial' && <small>{t(source.reason === 'SOURCE_EXTRACTION_PARTIAL'
      ? 'sourceContextExtractionPartial' : source.admittedChunks === 0 ? 'sourceContextNoExcerpt' : 'sourceContextPartialHint')}</small>}
    {source.errorCode && <details className="nova-source-context-diagnostic"><summary>{t('diagnosticDetails')}</summary><code>{source.errorCode}</code></details>}
  </li>)}</ul>
  return general?.collapsibleSourceContext ? <details className="nova-source-context nova-message-disclosure">
    <summary><NovaIcon name="chevron" size={13}/><span>{t('sourceContext')} · {sources.length}</span></summary>{list}
  </details> : <div className="nova-source-context" aria-label={t('sourceContext')}>{list}</div>
}

export function SourceReferences({citations}: {citations?: KnowledgeCitations}) {
  const {t} = useI18n()
  const count = (citations?.valid.length || 0) + (citations?.invalid.length || 0)
  if (!citations || !count) return null
  return <details className="nova-source-references nova-message-disclosure" aria-label={t('referencesTitle')}>
    <summary><NovaIcon name="chevron" size={13}/><span>{t('referencesTitle')} · {count}</span></summary>
    {!!citations.valid.length && <ul className="nova-source-reference-list">{citations.valid.map(citation => <li key={citation.citationId}>
      <span className="nova-source-reference-marker">[{citation.citationId}]</span>
      <NovaIcon name={sourceReferenceIcon(citation)} size={16}/>
      <div><strong>{citation.displayLabel}</strong><span>{sourceReferenceLocation(citation.locator, t)}</span></div>
    </li>)}</ul>}
    {!!citations.invalid.length && <p className="nova-source-reference-unavailable">{t('referenceUnverified')} {citations.invalid.map(id => `[${id}]`).join(', ')}</p>}
  </details>
}
